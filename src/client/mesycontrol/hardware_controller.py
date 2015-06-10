#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import weakref

import basic_model as bm
import hardware_model as hm
import protocol
import util

class ErrorResponse(Exception):
    pass

class Controller(object):
    """Link between hardware_model.MRC and MRCConnection.
    Reacts to changes to the connection state and updates the hardware model
    accordingly.
    """
    def __init__(self, connection):
        self.log        = util.make_logging_source_adapter(__name__, self)
        self.connection = connection
        self._mrc       = None

    def set_mrc(self, mrc):
        """Set the hardware_model.MRC instance this controller should work with."""
        if self.mrc is not None:
            self.mrc.set_disconnected()
            self.connection.disconnect(self.mrc)

        self._mrc = weakref.ref(mrc) if mrc is not None else None
        self.log.debug("set_mrc: %s", self.mrc)

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
                self.log.exception("read_parameter")
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
                self.log.exception("set_parameter")
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
                        self.mrc.remove_device(device)
                    elif idc > 0:
                        if device is None:
                            self.log.debug("scanbus: creating device (%d, %d, %d)", bus, addr, idc)
                            device = hm.Device(bus, addr, idc)
                            self.mrc.add_device(device)

                        device.idc = idc
                        device.rc  = bool(rc) if rc in (0, 1) else False
                        device.address_conflict = rc not in (0, 1)

            except Exception:
                self.log.exception("scanbus error")

        m = protocol.Message('request_scanbus', bus=bus)
        return self.connection.queue_request(m).add_done_callback(on_bus_scanned)
