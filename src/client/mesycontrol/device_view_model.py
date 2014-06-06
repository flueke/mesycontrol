#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import weakref
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import pyqtProperty

class DeviceViewModel(QtCore.QObject):
    sig_parameter_read    = pyqtSignal([str, int], [int, int])
    sig_parameter_set     = pyqtSignal([str, int], [int, int])
    sig_rc_set            = pyqtSignal(bool)

    def __init__(self, device_model, device_description, parent=None):
        super(DeviceViewModel, self).__init__(parent)

        self._device_model      = weakref.ref(device_model)
        self.device_description = device_description

        device_model.sig_parameter_read.connect(self._slt_parameter_read)
        device_model.sig_parameter_set.connect(self._slt_parameter_set)
        device_model.sig_rc_set.connect(self.sig_rc_set)

    def read_parameter(self, name_or_address, response_handler=None):
        self.device_model.read_parameter(self._name2address(name_or_address), response_handler)

    def set_parameter(self, name_or_address, value, response_handler = None):
        self.device_model.set_parameter(self._name2address(name_or_address), value, response_handler)

    def set_rc(self, on_off, response_handler=None):
        self.device_model.set_rc(on_off, response_handler)

    def get_device_model(self):
        return self._device_model() if self._device_model is not None else None

    def _name2address(self, name):
        address = self.device_description.get_parameter_by_name(name)
        if address is not None:
            return address
        return name

    def _slt_parameter_read(self, address, value):
        self.sig_parameter_read[int, int].emit(address, value)
        param_desc = self.device_description.get_parameter_by_address(address)
        if param_desc is not None and param_desc.name is not None:
           self.sig_parameter_read[str, int].emit(param_desc.name, value)

    def _slt_parameter_set(self, address, value):
        self.sig_parameter_set[int, int].emit(address, value)
        param_desc = self.device_description.get_parameter_by_address(address)
        if param_desc is not None and param_desc.name is not None:
           self.sig_parameter_set[str, int].emit(param_desc.name, value)

    device_model = pyqtProperty(object, get_device_model)

class MHV4ViewModel(DeviceViewModel):
    def __init__(self, device_model, device_description, parent=None):
        super(MHV4ViewModel, self).__init__(device_model, device_description, parent)

    def setChannelsEnabled(self, enabled):
        for i in range(4):
            self.set_parameter("channel%d_enable_write" % i, 1 if enabled else 0)

    def enableAllChannels(self):
        self.setChannelsEnabled(True)

    def disableAllChannels(self):
        self.setChannelsEnabled(False)
