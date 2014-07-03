#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import weakref
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import pyqtProperty
from . import application_model
from util import NamedObject

class DeviceModel(NamedObject):

    #: Signals that a parameter has been read.
    #: Args: [par_address, value] and [par_name, value]
    sig_parameter_read    = pyqtSignal([int, int], [str, int])

    #: Signals that a parameter has been set.
    #: Args: [par_address, value] and [par_name, value]
    sig_parameter_set     = pyqtSignal([int, int], [str, int])

    #: Only emitted if the value actually differs from the previously known
    #: value.
    #: Args: [par_address, old_value, new_value] and [par_name. old_value, new_value]
    sig_parameter_changed = pyqtSignal([int, int, int], [str, int, int])

    #: Signals that this devices RC flag has been set.
    sig_rc_set            = pyqtSignal(bool)

    #: Signal that this devices RC flag has changed.
    sig_rc_changed        = pyqtSignal(bool)

    #: Args: bus, dev
    sig_connected_to_bus  = pyqtSignal(int, int)

    #: Args: bus, dev
    sig_disconnected_from_bus    = pyqtSignal(int, int)

    #: Args: boolean, True if address conflict present
    sig_address_conflict_changed = pyqtSignal(bool)

    sig_connecting               = pyqtSignal()
    sig_connected                = pyqtSignal()
    sig_disconnected             = pyqtSignal()
    sig_connection_error         = pyqtSignal(object)
    sig_write_access_changed     = pyqtSignal(bool)
    sig_silence_changed          = pyqtSignal(bool)

    def __init__(self, bus, dev, idc, rc, mrc_model, parent=None):
        super(DeviceModel, self).__init__(parent=parent)
        self._mrc_model    = weakref.ref(mrc_model)
        self.bus           = bus
        self.dev           = dev
        self.idc           = idc
        self.rc            = rc
        self.memory        = {} # Map address -> value
        self.mirror_memory = {}
        self.description   = application_model.instance.get_device_description_by_idc(idc)
        self._disconnected_from_bus = False
        self._address_conflict      = False
        
        self.mrc_model.sig_parameter_read.connect(self._slt_parameterRead)
        self.mrc_model.sig_parameter_set.connect(self._slt_parameterSet)
        self.mrc_model.sig_rc_set.connect(self._slt_rc_set)
        self.mrc_model.sig_connecting.connect(self.sig_connecting)       
        self.mrc_model.sig_connected.connect(self.sig_connected)
        self.mrc_model.sig_disconnected.connect(self.sig_disconnected)
        self.mrc_model.sig_connection_error.connect(self.sig_connection_error)
        self.mrc_model.sig_write_access_changed.connect(self.sig_write_access_changed)
        self.mrc_model.sig_silence_changed.connect(self.sig_silence_changed)

    def read_parameter(self, address, response_handler=None):
        self.mrc_model.read_parameter(self.bus, self.dev, address, response_handler)

    def set_parameter(self, address, value, response_handler=None):
        self.mrc_model.set_parameter(self.bus, self.dev, address, value, response_handler)

    def set_rc(self, on_off, response_handler=None):
        self.mrc_model.set_rc(self.bus, self.dev, on_off, response_handler)

    def get_mrc_model(self):
        return self._mrc_model() if self._mrc_model is not None else None

    def is_connected(self):
        return self.mrc_model.is_connected if self.mrc_model is not None else False

    def set_disconnected_from_bus(self, is_disconnected):
        changed = self._disconnected_from_bus != is_disconnected
        self._disconnected_from_bus = is_disconnected

        if changed and is_disconnected:
            self.sig_disconnected_from_bus.emit(self.bus, self.dev)
        elif changed and not is_disconnected:
            self.sig_connected_to_bus.emit(self.bus, self.dev)

    def is_disconnected_from_bus(self):
        return self._disconnected_from_bus

    def is_connected_to_bus(self):
        return not self.is_disconnected_from_bus()

    def set_address_conflict(self, has_conflict):
        changed = self._address_conflict != has_conflict
        self._address_conflict = has_conflict
        if changed:
            self.sig_address_conflict_changed.emit(has_conflict)

    def has_address_conflict(self):
        return self._address_conflict

    def _slt_parameterRead(self, bus, dev, address, value):
        if bus == self.bus and dev == self.dev:
            old_value = self.memory.get(address, None)
            self.memory[address] = value
            self.sig_parameter_read.emit(address, value)

            param_descr = self.description.get_parameter_by_address(address)
            if param_descr is not None:
                self.sig_parameter_read[str, int].emit(param_descr.name, value)

            if old_value != value:
                self.sig_parameter_changed.emit(address, old_value, value)
                if param_descr is not None:
                    self.sig_parameter_changed[str, int, int].emit(param_descr.name, old_value, value)

    def _slt_parameterSet(self, bus, dev, address, value):
        if bus == self.bus and dev == self.dev:
            old_value = self.memory.get(address, None)
            self.memory[address] = value
            self.sig_parameter_set.emit(address, value)

            param_descr = self.description.get_parameter_by_address(address)
            if param_descr is not None:
                self.sig_parameter_set[str, int].emit(param_descr.name, value)

            if old_value != value:
                self.sig_parameter_changed.emit(address, old_value, value)
                if param_descr is not None:
                    self.sig_parameter_changed[str, int, int].emit(param_descr.name, old_value, value)

    def _slt_rc_set(self, bus, dev, on_off):
        if bus == self.bus and dev == self.dev:
            changed = self.rc != on_off
            self.rc = on_off
            self.sig_rc_set.emit(on_off)
            if changed:
                self.sig_rc_changed.emit(on_off)

    def __str__(self):
        if len(self.name):
            return "DeviceModel(%s, idc=%d, rc=%d)" % (self.name, self.idc, self.rc)
        return "DeviceModel(idc=%d, rc=%d)" % (self.idc, self.rc)

    mrc_model        = pyqtProperty(object, get_mrc_model)
    mrc              = pyqtProperty(object, get_mrc_model)
    connected        = pyqtProperty(bool, is_connected)
    connected_to_bus = pyqtProperty(bool, is_connected_to_bus)
    address_conflict = pyqtProperty(bool, has_address_conflict)
