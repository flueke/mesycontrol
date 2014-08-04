#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
import weakref

import util

class MRCModel(QtCore.QObject):
    #: State enum. 'Ready' state is entered once both busses have been scanned.
    Disconnected, Connecting, Connected, Ready = states = set(range(4))

    #: state_changed(old_state, new_state, new_state_info=None)
    state_changed  = pyqtSignal(int, int, object)

    #: bus_scanned(bus, data)
    bus_scanned    = pyqtSignal(int, object)

    #: device_added(DeviceModel)
    device_added   = pyqtSignal(object)

    #: device_removed(DeviceModel)
    device_removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super(MRCModel, self).__init__(parent)
        self.log             = util.make_logging_source_adapter(__name__, self)
        self._controller     = None
        self._devices        = list()
        self._busses_scanned = set()
        self._state          = MRCModel.Disconnected
        self._state_info     = None

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

        if self.state == MRCModel.Connected and len(self._busses_scanned) >= 2:
            self.state = MRCModel.Ready

    def set_parameter(self, bus, dev, par, val):
        self.get_device(bus, dev).set_parameter(par, val)

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
        self.devices.remove(device)
        device.setParent(None)
        self.device_removed.emit(device)

    def get_state(self):
        return self._state

    def get_state_info(self):
        return self._state_info

    def set_state(self, new_state, new_info=None):
        if new_state not in MRCModel.states:
            raise RuntimeError("MRCModel.set_state: invalid state")

        old_state        = self.state
        old_info         = self.state_info
        self._state      = new_state
        self._state_info = new_info

        if self.state == MRCModel.Disconnected:
            self._busses_scanned = set()

        if old_state != new_state or old_info != new_info:
            self.state_changed.emit(old_state, new_state, new_info)

    def is_connected(self):
        return self.state in (MRCModel.Connected, MRCModel.Ready)

    def is_ready(self):
        return self.state == MRCModel.Ready

    def get_controller(self):
        return self._controller

    def set_controller(self, controller):
        if self.controller is not None:
            self.controller.set_model(None)

        self.state       = MRCModel.Disconnected
        self._controller = controller

        if self.controller is not None:
            self.controller.set_model(self)

    state      = pyqtProperty(int,    get_state, set_state, notify=state_changed)
    state_info = pyqtProperty(object, get_state_info)
    connected  = pyqtProperty(bool,   is_connected)
    ready      = pyqtProperty(bool,   is_ready)
    controller = pyqtProperty(object, get_controller, set_controller)

class DeviceModel(QtCore.QObject):
    #: state enum
    Disconnected, Connecting, Connected, AddressConflict, Ready = states = set(range(5))

    #: state_changed(old_state, new_state, new_state_info=None)
    state_changed = pyqtSignal(int, int, object)

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
        self._state      = DeviceModel.Disconnected
        self._state_info = None
        self._bus        = bus
        self._address    = address
        self._idc        = idc
        self._rc         = rc
        self.reset_mem()
        self.reset_mirror()
        self.mrc         = mrc
        self.controller  = controller

    def set_mrc(self, mrc):
        if self.mrc is not None:
            # remove signal/slot connections
            self.mrc.disconnect(self)

        self.state = DeviceModel.Disconnected
        self._mrc  = weakref.ref(mrc) if mrc is not None else None

        if self.mrc is not None:
            self.mrc.state_changed.connect(self._on_mrc_state_changed)
            self._on_mrc_state_changed(MRCModel.Disconnected, mrc.state, mrc.state_info)

    def get_mrc(self):
        return self._mrc() if self._mrc is not None else None

    def get_state(self):
        return self._state

    def get_state_info(self):
        return self._state_info

    def set_state(self, new_state, new_info=None):
        if new_state not in DeviceModel.states:
            raise RuntimeError("DeviceModel.set_state: invalid state")

        old_state        = self.state
        old_info         = self.state_info
        self._state      = new_state
        self._state_info = new_info

        self.log.debug("DeviceModel.set_state: old_state=%d, new_state=%d, new_info=%s",
                old_state, new_state, new_info)

        if self.state == DeviceModel.Disconnected or (
                old_state == DeviceModel.AddressConflict and
                new_state != DeviceModel.AddressConflict):
            self.reset_mem()
            self.reset_mirror()

        if old_state != new_state or old_info != new_info:
            self.state_changed.emit(old_state, new_state, new_info)

    def set_address_conflict(self, b):
        if b:
            self.state = DeviceModel.AddressConflict
        elif self.mrc is not None and self.mrc.is_connected():
            self.state = DeviceModel.Connected
        else:
            self.state = DeviceModel.Disconnected

    def has_address_conflict(self):
        return self.state == DeviceModel.AddressConflict

    def is_connected(self):
        return self.state in (DeviceModel.Connected, DeviceModel.AddressConflict,
                DeviceModel.Ready)

    def is_ready(self):
        return self.state == DeviceModel.Ready

    def has_parameter(self, address):
        return address in self._memory

    def get_parameter(self, address):
        return self._memory[address]

    def set_parameter(self, address, value):
        old_value = self.get_parameter(address) if self.has_parameter(address) else None
        self._memory[address] = value

        if old_value != value:
            self.parameter_changed.emit(address, old_value, value)

        if self.state == DeviceModel.Connected and len(self._memory) >= 256:
            self.state = DeviceModel.Ready

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

    def _on_mrc_state_changed(self, old_state, new_state, info=None):
        self.log.debug("mrc_model state changed: mrc_model=%s, device_controller=%s", self.mrc, self.controller)
        self.log.debug("mrc_model state changed: old=%d, new=%d, info=%s", old_state, new_state, str(info))
        if new_state == MRCModel.Disconnected:
            self.set_state(DeviceModel.Disconnected, info)
        elif new_state == MRCModel.Connecting:
            self.set_state(DeviceModel.Connecting, info)
        elif new_state == MRCModel.Connected:
            self.set_state(DeviceModel.Connected, info)

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

        self._controller = controller
        if self.controller is not None:
            self.controller.set_model(self)

    state        = pyqtProperty(int,    get_state, set_state, notify=state_changed)
    state_info   = pyqtProperty(object, get_state_info)
    connected    = pyqtProperty(bool,   is_connected)
    ready        = pyqtProperty(bool,   is_ready)
    bus          = pyqtProperty(int,    get_bus)
    address      = pyqtProperty(int,    get_address)
    rc           = pyqtProperty(bool,   get_rc, set_rc, notify=rc_changed)
    idc          = pyqtProperty(int,    get_idc, set_idc, notify=idc_changed)
    memory       = pyqtProperty(dict,   get_memory)
    mirror       = pyqtProperty(dict,   get_mirror)
    controller   = pyqtProperty(object, get_controller, set_controller)
    mrc          = pyqtProperty(object, get_mrc, set_mrc)
