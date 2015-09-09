#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
import weakref

import basic_model as bm
import future
import hardware_model as hm
import proto
import util

# Polling, poll sets
# Read Range

class ErrorResponse(RuntimeError):
    pass

class TimeoutError(RuntimeError):
    def __str__(self):
        return "Connection timed out"

SCANBUS_INTERVAL_MSEC  = 5000
POLL_MIN_INTERVAL_MSEC =  500

class Controller(object):
    """Link between hardware_model.MRC and MRCConnection.
    Reacts to changes to the connection state and updates the hardware model
    accordingly. Also takes requests from the hardware model and forwards them
    to the connection.
    """
    def __init__(self, connection,
            scanbus_interval_msec=SCANBUS_INTERVAL_MSEC,
            poll_min_interval_msec=POLL_MIN_INTERVAL_MSEC):

        self.log        = util.make_logging_source_adapter(__name__, self)

        self.connection = connection
        self._mrc       = None
        self._scanbus_timer = QtCore.QTimer()
        self._scanbus_timer.timeout.connect(self._on_scanbus_timer_timeout)
        self.set_scanbus_interval(scanbus_interval_msec)

        self._poll_timer = QtCore.QTimer()
        self._poll_timer.timeout.connect(self._on_poll_timer_timeout)
        self._poll_items = weakref.WeakKeyDictionary()
        self.set_poll_min_interval(poll_min_interval_msec)

        self._connect_timer = QtCore.QTimer()
        self._connect_timer.setSingleShot(True)
        self._connect_timer.timeout.connect(self._on_connect_timer_timeout)
        self._connect_future = None

        def on_connected():
            for i in bm.BUS_RANGE:
                self.scanbus(i)

            self._scanbus_timer.start()
            self._poll_timer.start()

        def on_disconnected():
            self._scanbus_timer.stop()
            self._poll_timer.stop()

        self.connection.connected.connect(on_connected)
        self.connection.disconnected.connect(on_disconnected)
        self.connection.notification_received.connect(self._on_notification_received)

    def set_mrc(self, mrc):
        """Set the hardware_model.MRC instance this controller should work with."""
        self.log.debug("set_mrc: old=%s, new=%s", self.mrc, mrc)
        if self.mrc is not None:
            self.mrc.set_disconnected()
            self.connection.connected.disconnect(self.mrc.set_connected)
            self.connection.connecting.disconnect(self.mrc.set_connecting)
            self.connection.disconnected.disconnect(self.mrc.set_disconnected)
            self.connection.connection_error.disconnect(self.mrc.set_connection_error)

        self._mrc = weakref.ref(mrc) if mrc is not None else None

        if self.mrc is not None:
            self.mrc.url = self.connection.url
            if self.connection.is_connected():
                self.mrc.set_connected()

            if self.connection.is_connecting():
                self.mrc.set_connecting()

            if self.connection.is_disconnected():
                self.mrc.set_disconnected()

            self.connection.connected.connect(self.mrc.set_connected)
            self.connection.connecting.connect(self.mrc.set_connecting)
            self.connection.disconnected.connect(self.mrc.set_disconnected)
            self.connection.connection_error.connect(self.mrc.set_connection_error)

    def get_mrc(self):
        return self._mrc() if self._mrc is not None else None

    mrc = property(get_mrc, set_mrc)

    def connect(self, timeout_ms=hm.DEFAULT_CONNECT_TIMEOUT_MS):
        self.log.debug("connect: timeout_ms=%s", timeout_ms)

        self._connect_future = future.Future()

        def on_connection_connected(f):
            if self._connect_future is None or self._connect_future.done():
                return

            if f.exception() is not None:
                self._connect_future.set_exception(f.exception())
            else:
                self._connect_future.set_result(f.result())

        f = self.connection.connect().add_done_callback(on_connection_connected)
        future.progress_forwarder(f, self._connect_future)

        if timeout_ms > 0:
            self._connect_timer.start(timeout_ms)

        return self._connect_future

    def disconnect(self):
        return self.connection.disconnect()

    def read_parameter(self, bus, device, address):
        """Read the parameter at (bus, device address).
        Returns a basic_model.ResultFuture containing a basic_model.ReadResult
        instance on success.
        """
        ret = bm.ResultFuture()

        def on_response_received(f):
            try:
                ret.set_result(bm.ReadResult(bus, device, address, f.result().response.response_read.val))
            except Exception as e:
                ret.set_exception(e)

        m = proto.Message()
        m.type = proto.Message.REQ_READ
        m.request_read.bus      = bus
        m.request_read.dev      = device
        m.request_read.par      = address
        m.request_read.mirror   = False

        request_future = self.connection.queue_request(m).add_done_callback(
                on_response_received)

        def cancel_request(f):
            if f.cancelled():
                request_future.cancel()

        ret.add_done_callback(cancel_request)

        return ret

    def set_parameter(self, bus, device, address, value):
        """Set the parameter at (bus, device, address) to the given value.
        Returns a basic_model.ResultFuture containing a basic_model.SetResult
        instance on success.
        """
        ret = bm.ResultFuture()

        def on_response_received(f):
            try:
                if not f.cancelled():
                    ret.set_result(bm.SetResult(bus, device, address, f.result().response.set_result.val, value))
            except Exception as e:
                if not ret.done():
                    ret.set_exception(e)

        m = proto.Message()
        m.type = proto.Message.REQ_SET
        m.request_set.bus       = int(bus)
        m.request_set.dev       = int(device)
        m.request_set.par       = int(address)
        m.request_set.val       = int(value)
        m.request_set.mirror    = False
        request_future = self.connection.queue_request(m).add_done_callback(on_response_received)

        def cancel_request(f):
            if f.cancelled():
                request_future.cancel()

        ret.add_done_callback(cancel_request)

        return ret

    def scanbus(self, bus):
        def on_bus_scanned(f):
            try:
                bus     = f.result().response.scanbus_result.bus
                entries = f.result().response.scanbus_result.entries

                self.log.debug("%s: received scanbus response %d: %s", self, bus, entries)

                for addr in bm.DEV_RANGE:
                    entry    = entries[addr]
                    idc      = entry.idc
                    rc       = entry.rc
                    conflict = entry.conflict

                    device  = self.mrc.get_device(bus, addr)

                    if idc <= 0 and device is not None:
                        self.log.debug("%s: scanbus: removing device (%d, %d)", self, bus, addr)
                        self.mrc.remove_device(device)
                    elif idc > 0:
                        if device is None:
                            self.log.debug("%s: scanbus: creating device (%d, %d, idc=%d)", self, bus, addr, idc)
                            device = hm.Device(bus, addr, idc)
                            self.mrc.add_device(device)

                        device.idc = idc
                        device.rc  = rc
                        device.address_conflict = conflict

                        if device.address_conflict:
                            self.log.debug("%s: scanbus: address conflict on (%d, %d)", self, bus, addr)

                self.mrc.address_conflict = any((d.address_conflict for d in self.mrc))

            except Exception:
                self.log.exception("%s: scanbus error" % self)

        m = proto.Message()
        m.type = proto.Message.REQ_SCANBUS
        m.request_scanbus.bus = bus
        return self.connection.queue_request(m).add_done_callback(on_bus_scanned)

    def set_rc(self, bus, device, on_off):
        m = proto.Message()
        m.type = proto.Message.REQ_RC
        m.request_rc.bus = bus
        m.request_rc.dev = device
        m.request_rc.rc  = on_off
        return self.connection.queue_request(m)

    def set_scanbus_interval(self, msec):
        self._scanbus_timer.setInterval(msec)

    def get_scanbus_interval(self):
        return self._scanbus_timer.interval()

    def _on_scanbus_timer_timeout(self):
        if self.connection.is_connected():
            for i in bm.BUS_RANGE:
                self.scanbus(i)

    def set_poll_min_interval(self, msec):
        self._poll_timer.setInterval(msec)

    def get_poll_min_interval(self):
        return self._poll_timer.interval()

    #def _on_poll_timer_timeout(self):
    #    if not self.connection.is_connected():
    #        return

    #    if self.connection.get_queue_size() > 0:
    #        return

    #    if len(self._poll_items):
    #        self.log.debug("%s: polling subscribers: %s",
    #                self, self._poll_items.keys())

    #    # Merge all poll items into one set.
    #    # Note: This does not try to merge any overlapping ranges. Those will
    #    # lead to parameters being read multiple times.
    #    items = reduce(lambda x, y: x.union(y), self._poll_items.values(), set())

    #    polled_items_by_device = dict()

    #    for bus, dev, item in items:
    #        device = self.mrc.get_device(bus, dev)
    #        if not device or not device.polling:
    #            continue

    #        polled_items = polled_items_by_device.setdefault((bus, dev), set())

    #        # Note: below device.read_parameter() is used instead of
    #        # self.read_parameter(). This ensures the device can update its
    #        # memory cache and keep track of reads in progress.
    #        try:
    #            lower, upper = item
    #            polled_items.add((lower, upper))
    #            for param in xrange(lower, upper+1):
    #                device.read_parameter(param)
    #        except TypeError:
    #            polled_items.add(item)
    #            device.read_parameter(item)

    #    for bus, dev in sorted(polled_items_by_device.keys()):
    #        self.log.debug("%s: polled (%d, %d): %s", self, bus, dev,
    #                sorted(polled_items_by_device[(bus, dev)]))

    def _on_poll_timer_timeout(self):
        if not self.connection.is_connected():
            return

        # Merge all poll items into one set.
        # Note: This does not try to merge any overlapping ranges. Those will
        # lead to parameters being read multiple times.
        items = reduce(lambda x, y: x.union(y), self._poll_items.values(), set())

        if not len(items):
            return

        m = proto.Message()
        m.type = proto.Message.REQ_SET_POLL_ITEMS

        for bus, dev, item in items:
            proto_item = m.request_set_poll_items.items.add()
            proto_item.bus = bus
            proto_item.dev = dev

            try:
                lower, upper = item
                proto_item.par   = lower
                proto_item.count = (upper - lower) + 1
            except TypeError:
                proto_item.par   = item
                proto_item.count = 1

        self.connection.queue_request(m)

    def add_poll_item(self, subscriber, bus, address, item):
        """Add a poll subscription for the given (bus, address, item). Item may
        be a single parameter address or a tuple of (lower, upper) addresses to
        poll. The poll item is removed if the given subscriber is destroyed."""
        items = self._poll_items.setdefault(subscriber, set())
        items.add((bus, address, item))

    def remove_polling_subscriber(self, subscriber):
        try:
            del self._poll_items[subscriber]
        except KeyError:
            pass

    def _on_connect_timer_timeout(self):
        if self._connect_future is not None and not self._connect_future.done():
            self.log.debug("_on_connect_timer_timeout: TimeoutError, %s", self._connect_future)
            self._connect_future.set_exception(TimeoutError(self.connection.url))
            self._connect_future = None
            self.connection.disconnect()

    def __str__(self):
        return "Controller(%s)" % util.display_url(self.connection.url)

    def _on_notification_received(self, msg):
        if msg.type == proto.Message.NOTIFY_MRC_STATUS:
            self.mrc.set_status(msg)
