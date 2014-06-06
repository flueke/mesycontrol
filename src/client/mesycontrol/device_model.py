#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import weakref
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import pyqtProperty

class DeviceModel(QtCore.QObject):
    #: Args: par, val
    sig_parameter_read = pyqtSignal(int, int)
    #: Args: par, val
    sig_parameter_set = pyqtSignal(int, int)
    #: Args: par, old_val, new_val. Only emitted if the value actually differs
    #: from the previously known value.
    sig_parameterChanged = pyqtSignal(int, int, int)
    #: Arg: rc_status
    sig_rc_set = pyqtSignal(bool)

    def __init__(self, bus, dev, idc, rc, mrc_model, parent=None):
        super(DeviceModel, self).__init__(parent)
        self._mrc_model = weakref.ref(mrc_model)
        self.bus       = bus
        self.dev       = dev
        self.idc       = idc
        self.rc        = rc
        self.memory   = {}
        
        self.mrc_model.sig_parameter_read.connect(self._slt_parameterRead)
        self.mrc_model.sig_parameter_set.connect(self._slt_parameterSet)
        self.mrc_model.sig_rc_set.connect(self._slt_rcSet)

    def read_parameter(self, address, response_handler=None):
        self.mrc_model.read_parameter(self.bus, self.dev, address, response_handler)

    def set_parameter(self, address, value, response_handler=None):
        self.mrc_model.set_parameter(self.bus, self.dev, address, value, response_handler)

    def set_rc(self, on_off, response_handler=None):
        self.mrc_model.set_rc(self.bus, self.dev, on_off, response_handler)

    def getMRCModel(self):
        return self._mrc_model() if self._mrc_model is not None else None

    def _slt_parameterRead(self, bus, dev, address, value):
        if bus == self.bus and dev == self.dev:
            old_value = self.memory.get(address, None)
            self.memory[address] = value
            self.sig_parameter_read.emit(address, value)
            if old_value != value:
                self.sig_parameterChanged.emit(address, old_value, value)

    def _slt_parameterSet(self, bus, dev, address, value):
        if bus == self.bus and dev == self.dev:
            old_value = self.memory.get(address, None)
            self.memory[address] = value
            self.sig_parameter_set.emit(address, value)
            if old_value != value:
                self.sig_parameterChanged.emit(address, old_value, value)

    def _slt_rcSet(self, bus, dev, on_off):
        if bus == self.bus and dev == self.dev:
            self.rc = on_off
            self.sig_rc_set.emit(on_off)

    def __str__(self):
        return "DeviceModel(idc=%d, rc=%d)" % (self.idc, self.rc)

    mrc_model = pyqtProperty(object, getMRCModel)


