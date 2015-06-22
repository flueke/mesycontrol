#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
import weakref

import basic_model as bm
import hardware_model as hm
import protocol
import util

# Periodic scanbus
# Wie? timer
# Polling, poll sets
# Read Range

class ErrorResponse(Exception):
    pass

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

    def connect(self):
        return self.connection.connect()

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
                ret.set_result(bm.ReadResult(bus, device, address, f.result().response.val))
            except Exception as e:
                #self.log.exception("read_parameter")
                ret.set_exception(e)

        m = protocol.Message('request_read', bus=bus, dev=device, par=address)
        self.connection.queue_request(m).add_done_callback(on_response_received)

        return ret

    def set_parameter(self, bus, device, address, value):
        """Set the parameter at (bus, device, address) to the given value.
        Returns a basic_model.ResultFuture containing a basic_model.SetResult
        instance on success.
        """
        ret = bm.ResultFuture()

        def on_response_received(f):
            try:
                ret.set_result(bm.SetResult(bus, device, address, f.result().response.val, value))
            except Exception as e:
                #self.log.exception("set_parameter")
                ret.set_exception(e)

        m = protocol.Message('request_set', bus=bus, dev=device, par=address, val=value)
        self.connection.queue_request(m).add_done_callback(on_response_received)

        return ret

    def scanbus(self, bus):
        def on_bus_scanned(f):
            try:
                data = f.result().response.bus_data

                self.log.debug("scanbus: received response: %s", data)

                for addr in bm.DEV_RANGE:
                    idc, rc = data[addr]
                    device  = self.mrc.get_device(bus, addr)

                    if idc <= 0 and device is not None:
                        self.log.debug("scanbus: removing device (%d, %d)", bus, addr)
                        self.mrc.remove_device(device)
                    elif idc > 0:
                        if device is None:
                            self.log.debug("scanbus: creating device (%d, %d, idc=%d)", bus, addr, idc)
                            device = hm.Device(bus, addr, idc)
                            self.mrc.add_device(device)

                        device.idc = idc
                        device.rc  = bool(rc) if rc in (0, 1) else False
                        device.address_conflict = rc not in (0, 1)

                        if device.address_conflict:
                            self.log.debug("scanbus: address conflict on (%d, %d)", bus, addr)

                self.mrc.address_conflict = any((d.address_conflict for d in self.mrc))

            except Exception:
                self.log.exception("scanbus error")

        m = protocol.Message('request_scanbus', bus=bus)
        return self.connection.queue_request(m).add_done_callback(on_bus_scanned)

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

    def _on_poll_timer_timeout(self):
        if not self.connection.is_connected():
            return

        if self.connection.get_queue_size() > 0:
            return

        # Merge all poll items into one set.
        # Note: This does not try to merge any overlapping ranges. Those will
        # lead to parameters being read multiple times.
        items = reduce(lambda x, y: x.union(y), self._poll_items.values(), set())

        for bus, dev, item in items:
            device = self.mrc.get_device(bus, dev)
            if not device or not device.polling:
                continue
            try:
                lower, upper = item
                for param in xrange(lower, upper+1):
                    self.read_parameter(bus, dev, param)
            except TypeError:
                self.read_parameter(bus, dev, item)

    def add_poll_item(self, subscriber, bus, address, item):
        items = self._poll_items.setdefault(subscriber, set())
        items.add((bus, address, item))
