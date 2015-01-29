#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
import weakref
import sys

import util

class MRCModel(QtCore.QObject):
    connecting               = pyqtSignal()
    connected                = pyqtSignal()
    disconnected             = pyqtSignal(object) #: error object or None
    ready                    = pyqtSignal(bool)

    #: bus_scanned(bus, data)
    bus_scanned    = pyqtSignal(int, object)

    #: device_added(DeviceModel)
    device_added   = pyqtSignal(object)

    #: device_removed(DeviceModel)
    device_removed = pyqtSignal(object)

    polling_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super(MRCModel, self).__init__(parent)
        self.log               = util.make_logging_source_adapter(__name__, self)
        self._controller       = None
        self._devices          = list()
        self._busses_scanned   = set()
        self._connected        = False
        self._connecting       = False
        self._connection_error = None

    def set_scanbus_data(self, bus, data):
        for addr in range(16):
            idc, rc = data[addr]
            device  = self.get_device(bus, addr)

            if idc <= 0 and device is not None:
                self.log.debug("%s @ (%d,%d) disappeared", device, bus, addr)
                self._remove_device(device)
            elif idc > 0:
                if device is None:
                    device_controller = self.controller.make_device_controller() if self.controller is not None else None
                    device = DeviceModel(bus, addr, idc, rc if rc in (0, 1) else False, controller=device_controller, mrc=self)
                    self.add_device(device)
                device.idc = idc
                device.set_address_conflict(rc not in (0, 1))
                device.set_rc(bool(rc) if rc in (0, 1) else False)

        self._busses_scanned.add(bus)
        self.bus_scanned.emit(bus, data)

        if self.is_ready():
            self.ready.emit(True)

    def set_parameter(self, bus, dev, par, val, force_emit_change=False):
        self.get_device(bus, dev).set_parameter(par, val, force_emit_change)

    def set_mirror_parameter(self, bus, dev, par, val):
        self.get_device(bus, dev).set_mirror_parameter(par, val)

    def set_rc(self, bus, dev, on_off):
        self.get_device(bus, dev).set_rc(on_off)

    def reset_mem(self, bus, dev):
        self.get_device(bus, dev).reset_mem()

    def reset_mirror(self, bus, dev):
        self.get_device(bus, dev).reset_mirror()

    def has_device(self, bus, address):
        return self.get_device(bus, address) is not None

    def get_device(self, bus, address):
        try:
            return filter(lambda d: d.bus == bus and d.address == address, self._devices)[0]
        except IndexError:
            return None

    def get_devices(self, bus=None):
        if bus is None:
            return list(self._devices)
        return filter(lambda d: d.bus == bus, self._devices)
                    
    def add_device(self, device):
        if self.has_device(device.bus, device.address):
            raise RuntimeError("Device exists (bus=%d, address=%d)" %
                    (device.bus, device.address))
        self._devices.append(device)
        self.device_added.emit(device)

    def _remove_device(self, device):
        self._devices.remove(device)
        device.mrc = None
        self.device_removed.emit(device)

    def set_connected(self):
        self._connected      = True
        self._connecting     = False
        self._busses_scanned = set()
        self.connected.emit()

    def set_connecting(self):
        self._connected  = False
        self._connecting = True
        self.connecting.emit()

    def set_disconnected(self, error=None):
        self._connected         = False
        self._connecting        = False
        self._connection_error  = error
        self._busses_scanned    = set()
        self.disconnected.emit(error)
        self.ready.emit(self.is_ready())

    def is_connecting(self):
        return self._connecting

    def is_connected(self):
        return self._connected

    def is_disconnected(self):
        return not self._connected

    def is_ready(self):
        return self.is_connected() and self._busses_scanned == set((0, 1))

    def get_controller(self):
        return self._controller

    def set_controller(self, controller):
        if self.controller is not None:
            self.controller.set_model(None)
            self.controller.polling_changed.disconnect(self.polling_changed)

        self._controller = controller

        if self.controller is not None:
            self.controller.set_model(self)
            self.controller.polling_changed.connect(self.polling_changed)

    def get_connection_info(self):
        if self.controller is not None:
            return self.controller.get_connection_info()
        return None

    def should_poll(self):
        return self.controller.should_poll()

    def set_polling_enabled(self, on_off):
        self.controller.set_polling_enabled(on_off)

    controller  = pyqtProperty(object, get_controller, set_controller)
    polling     = pyqtProperty(bool,   should_poll, set_polling_enabled, notify=polling_changed)

class DeviceModel(QtCore.QObject):
    connecting      = pyqtSignal()
    connected       = pyqtSignal()
    disconnected    = pyqtSignal(object) #: error object or None
    polling_changed = pyqtSignal(bool)

    #: idc_changed(idc)
    idc_changed   = pyqtSignal(int)

    #: rc_changed(rc)
    rc_changed    = pyqtSignal(bool)

    #: address_conflict_changed(bool)
    address_conflict_changed = pyqtSignal(bool)

    #: parameter_changed(address, old_value, new_value)
    parameter_changed        = pyqtSignal(int, int, int)

    #: mirror_parameter_changed(address, old_value, new_value)
    mirror_parameter_changed = pyqtSignal(int, int, int)

    memory_reset = pyqtSignal()
    mirror_reset = pyqtSignal()

    def __init__(self, bus, address, idc, rc, controller=None, mrc=None, parent=None):
        super(DeviceModel, self).__init__(parent)
        self.log         = util.make_logging_source_adapter(__name__, self)

        self.log.debug("DeviceModel: bus=%d, address=%d, idc=%d, rc=%d, controller=%s, mrc=%s",
                bus, address, idc, rc, controller, mrc)

        self._controller = None
        self._mrc        = None
        self._bus        = int(bus)
        self._address    = int(address)
        self._idc        = int(idc)
        self._rc         = bool(rc)

        self.reset_mem()
        self.reset_mirror()

        self.mrc         = mrc
        self.controller  = controller

    def set_mrc(self, mrc):
        if self.mrc is not None:
            self.mrc.connected.disconnect(self.connected)
            self.mrc.connecting.disconnect(self.connecting)
            self.mrc.disconnected.disconnect(self._on_mrc_disconnected)

        self._mrc  = weakref.ref(mrc) if mrc is not None else None

        if self.mrc is not None:
            self.mrc.connected.connect(self.connected)
            self.mrc.connecting.connect(self.connecting)
            self.mrc.disconnected.connect(self._on_mrc_disconnected)

    def get_mrc(self):
        return self._mrc() if self._mrc is not None else None

    def has_mrc(self):
        return self.mrc is not None

    def set_address_conflict(self, b):
        self._address_confilct = b
        self.address_conflict_changed.emit(b)

    def has_address_conflict(self):
        return self._address_confilct

    def is_connecting(self):
        if not self.has_mrc():
            return False
        return self.mrc.is_connecting()

    def is_connected(self):
        if not self.has_mrc():
            return False
        return self.mrc.is_connected()

    def is_disconnected(self):
        if not self.has_mrc():
            return True
        return self.mrc.is_disconnected()

    def has_parameter(self, address):
        return address in self._memory

    def get_parameter(self, address):
        return self._memory[address]

    def set_parameter(self, address, value, force_emit_change=False):
        """Sets the devices parameter at `address' to `value'.
        Emit `parameter_changed' if the parameter changes value or
        `force_emit_change' is True.
        """
        old_value = self.get_parameter(address) if self.has_parameter(address) else -sys.maxint - 1
        self._memory[address] = value

        if old_value != value or force_emit_change:
            self.parameter_changed.emit(address, old_value, value)

    def has_mirror_parameter(self, address):
        return address in self._mirror

    def get_mirror_parameter(self, address):
        return self._mirror[address]

    def set_mirror_parameter(self, address, value):
        old_value = self.get_mirror_parameter(address) if self.has_mirror_parameter(address) else None
        self._mirror[address] = value

        if old_value != value:
            self.mirror_parameter_changed.emit(address, old_value, value)

    def reset_mem(self):
        self._memory = dict()
        self.memory_reset.emit()

    def reset_mirror(self):
        self._mirror = dict()
        self.mirror_reset.emit()

    def get_bus(self):
        return self._bus

    def get_address(self):
        return self._address

    def get_rc(self):
        return self._rc

    def set_rc(self, on_off):
        if self.rc != on_off:
            self._rc = on_off
            self.rc_changed.emit(self.rc)

    def get_idc(self):
        return self._idc

    def set_idc(self, idc):
        if self.idc != idc:
            self._idc = idc
            self.idc_changed.emit(self.idc)

    def get_memory(self):
        return dict(self._memory)

    def get_mirror(self):
        return dict(self._mirror)

    def get_controller(self):
        return self._controller

    def set_controller(self, controller):
        if self.controller is not None:
            self.controller.set_model(None)
            self.controller.polling_changed.disconnect(self.polling_changed)

        self._controller = controller

        if self.controller is not None:
            self.controller.set_model(self)
            self.controller.polling_changed.connect(self.polling_changed)

    def _on_mrc_disconnected(self):
        self.reset_mem()
        self.reset_mirror()
        self.disconnected.emit(None)

    def should_poll(self):
        return self.controller.should_poll()

    def set_polling_enabled(self, on_off):
        self.controller.set_polling_enabled(on_off)

    bus          = pyqtProperty(int,    get_bus)
    address      = pyqtProperty(int,    get_address)
    rc           = pyqtProperty(bool,   get_rc, set_rc, notify=rc_changed)
    idc          = pyqtProperty(int,    get_idc, set_idc, notify=idc_changed)
    memory       = pyqtProperty(dict,   get_memory)
    mirror       = pyqtProperty(dict,   get_mirror)
    controller   = pyqtProperty(object, get_controller, set_controller)
    mrc          = pyqtProperty(object, get_mrc, set_mrc)
    polling      = pyqtProperty(bool,   should_poll, set_polling_enabled)
