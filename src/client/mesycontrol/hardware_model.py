#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtProperty

import basic_model as bm
import util

class MRC(bm.MRC):
    def __init__(self, url, parent=None):
        super(MRC, self).__init__(url, parent)
        self.log   = util.make_logging_source_adapter(__name__, self)
        self.controller = None
        self.connection = None

    def set_connection(self, connection):
        self._connection = connection
        if self.controller is not None:
            self.controller.connection = self.connection

    def get_connection(self):
        return self._connection

    def set_controller(self, controller):
        self._controller = controller
        if self.controller is not None:
            self.controller.mrc = self
            self.controller.connection = self.connection

    def get_controller(self):
        return self._controller

    connection = pyqtProperty(object, get_connection, set_connection)
    controller = pyqtProperty(object, get_controller, set_controller)

    def connect(self):
        return self.connection.connect()

    def disconnect(self):
        return self.connection.disconnect()

    def is_connected(self):
        return self.connection.is_connected()

    def is_connecting(self):
        return self.connection.is_connecting()

    def is_disconnected(self):
        return self.connection.is_disconnected()

    def read_parameter(self, bus, device, address):
        return self.controller.read_parameter(bus, device, address)

    def set_parameter(self, bus, device, address, value):
        return self.controller.set_parameter(self, bus, device, address, value)

    def scanbus(self, bus):
        return self.controller.scanbus(bus)

class Device(bm.Device):
    def __init__(self, bus, address, idc, parent=None):
        super(Device, self).__init__(bus, address, idc, parent)

    def read_parameter(self, address):
        def on_parameter_read(f):
            try:
                self.set_cached_parameter(address, int(f))
            except Exception:
                self.log.exception("read_parameter")

        ret = self.mrc.read_parameter(self.bus, self.address, address)
        ret.add_done_callback(on_parameter_read)
        return ret

    def set_parameter(self, address, value):
        def on_parameter_set(f):
            try:
                self.set_cached_parameter(address, int(f))
            except Exception:
                self.log.exception("set_parameter")

        ret = self.mrc.set_parameter(self.bus, self.address, address, value)
        ret.add_done_callback(on_parameter_set)
        return ret

    def get_controller(self):
        return self.mrc.controller

    controller = pyqtProperty(object, get_controller)
