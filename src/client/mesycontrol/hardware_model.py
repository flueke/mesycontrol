#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtProperty
from qt import pyqtSignal

import basic_model as bm
import util

DEFAULT_CONNECT_TIMEOUT_MS = 10000

class AddressConflict(RuntimeError):
    pass

class MRC(bm.MRC):
    connected                   = pyqtSignal()
    connecting                  = pyqtSignal(object)    #: future object
    disconnected                = pyqtSignal()
    connection_error            = pyqtSignal(object)    #: error object

    address_conflict_changed    = pyqtSignal(bool)
    polling_changed             = pyqtSignal(bool)


    def __init__(self, url, parent=None):
        super(MRC, self).__init__(url, parent)
        self.log   = util.make_logging_source_adapter(__name__, self)
        self._controller = None

        self._connected  = False
        self._connecting = False
        self._disconnected = True
        self._polling = True
        self.last_connection_error = None

    def set_controller(self, controller):
        """Set the hardware controller this MRC should use.
        The MRC holds a strong reference to the controller."""
        if self.controller is not None:
            self.controller.mrc = None

        self._controller = controller

        if self.controller is not None:
            self.controller.mrc = self

    def get_controller(self):
        return self._controller

    def add_device(self, device):
        super(MRC, self).add_device(device)

        self.connected.connect(device.connected)
        self.connecting.connect(device.connecting)
        self.disconnected.connect(device.disconnected)
        self.connection_error.connect(device.connection_error)

    def remove_device(self, device):
        super(MRC, self).remove_device(device)

        self.connected.disconnect(device.connected)
        self.connecting.disconnect(device.connecting)
        self.disconnected.disconnect(device.disconnected)
        self.connection_error.disconnect(device.connection_error)

    def get_connection(self):
        return self.controller.connection

    def connect(self, timeout_ms=DEFAULT_CONNECT_TIMEOUT_MS):
        ret = self.controller.connect(timeout_ms)
        self.set_connecting(ret)
        return ret

    def disconnect(self):
        return self.controller.disconnect()

    def is_connected(self):
        return self._connected

    def set_connected(self):
        self.log.debug("%s: set_connected", self.url)
        self._connected, self._connecting, self._disconnected = (True, False, False)
        self.last_connection_error = None
        self.connected.emit()

    def is_connecting(self):
        return self._connecting

    def set_connecting(self, the_future):
        self.log.debug("%s: set_connecting", self.url)
        self._connected, self._connecting, self._disconnected = (False, True, False)
        self.last_connection_error = None
        self.connecting.emit(the_future)

    def is_disconnected(self):
        return self._disconnected

    def set_disconnected(self):
        self.log.debug("%s: set_disconnected", self.url)
        self._connected, self._connecting, self._disconnected = (False, False, True)
        self.disconnected.emit()
        for device in self:
            device.clear_cached_memory()

    def set_connection_error(self, error):
        self.log.debug("%s: set_connection_error", self.url)
        self._connected, self._connecting, self._disconnected = (False, False, True)
        self.last_connection_error = error
        self.connection_error.emit(error)
        for device in self:
            device.clear_cached_memory()

    def read_parameter(self, bus, device, address):
        return self.controller.read_parameter(bus, device, address)

    def set_parameter(self, bus, device, address, value):
        return self.controller.set_parameter(bus, device, address, value)

    def scanbus(self, bus):
        return self.controller.scanbus(bus)

    def should_poll(self):
        return self._polling

    def set_polling(self, on_off):
        on_off = bool(on_off)
        if self._polling != on_off:
            self._polling = on_off
            self.polling_changed.emit(on_off)

    connection  = pyqtProperty(object, get_connection)
    controller  = pyqtProperty(object, get_controller, set_controller)
    polling     = pyqtProperty(bool, should_poll, set_polling, notify=polling_changed)

class Device(bm.Device):
    connected                   = pyqtSignal()
    connecting                  = pyqtSignal(object)
    disconnected                = pyqtSignal()
    connection_error            = pyqtSignal(object)    #: error object

    address_conflict_changed    = pyqtSignal(bool)
    rc_changed                  = pyqtSignal(bool)
    polling_changed             = pyqtSignal(bool)

    def __init__(self, bus, address, idc, parent=None):
        super(Device, self).__init__(bus, address, idc, parent)

        self._address_conflict = False
        self._rc = False
        self._polling = True

    def _read_parameter(self, address):
        if self.address_conflict:
            raise AddressConflict()
        return self.mrc.read_parameter(self.bus, self.address, address)

    def _set_parameter(self, address, value):
        if self.address_conflict:
            raise AddressConflict()
        return self.mrc.set_parameter(self.bus, self.address, address, value)

    def get_controller(self):
        return self.mrc.controller

    def has_address_conflict(self):
        return self._address_conflict

    def set_address_conflict(self, conflict):
        conflict = bool(conflict)
        if self.address_conflict != conflict:
            self._address_conflict = conflict
            self.address_conflict_changed.emit(self.address_conflict)

    def get_rc(self):
        return self._rc

    def update_rc(self, rc):
        """Updates the local RC flag of this device."""
        rc = bool(rc)
        if self.rc != rc:
            self._rc = rc
            self.rc_changed.emit(self.rc)

    def set_rc(self, on_off):
        """Sends a ON/OFF command to the MRC.
        On successful command execution the local RC flag is updated.
        """
        if self.address_conflict:
            raise AddressConflict()

        def on_rc_set(f):
            if f.exception() is None:
                self.update_rc(on_off)

        ret = self.controller.set_rc(self.bus, self.address, on_off)
        ret.add_done_callback(on_rc_set)
        return ret

    def should_poll(self):
        return self.mrc.polling and self._polling

    def set_polling(self, on_off):
        on_off = bool(on_off)
        if self._polling != on_off:
            self._polling = on_off
            self.polling_changed.emit(on_off)

    def add_poll_item(self, subscriber, item):
        """Add parameters that should be polled repeatedly.
        As long as the given subscriber object is alive and polling is enabled
        for this device and the device is connected, the given item will be
        polled.
        Item may be a single parameter address or a tuple of (lower, upper)
        addresses to poll.
        If the server and mrc support reading parameter ranges and a tuple is
        given, the read range command will be used."""
        self.controller.add_poll_item(subscriber, self.bus, self.address, item)

    def remove_polling_subscriber(self, subscriber):
        return self.controller.remove_polling_subscriber(subscriber)

    def is_connected(self):
        return self.mrc.is_connected()

    def is_connecting(self):
        return self.mrc.is_connecting()

    def is_disconnected(self):
        return self.mrc.is_disconnected()

    def get_last_connection_error(self):
        return self.mrc.last_connection_error

    def __str__(self):
        return "%s.Device(id=%s, b=%d, a=%d, idc=%d, mrc=%s)" % (
                __name__, hex(id(self)), self.bus, self.address, self.idc, self.mrc)

    controller = pyqtProperty(object, get_controller)

    address_conflict = pyqtProperty(bool, has_address_conflict, set_address_conflict,
            notify=address_conflict_changed)

    rc = pyqtProperty(bool, get_rc, update_rc, notify=rc_changed)
    polling = pyqtProperty(bool, should_poll, set_polling, notify=polling_changed)
