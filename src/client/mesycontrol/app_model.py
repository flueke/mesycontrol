#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
import weakref

from device_description import DeviceDescription

class MRC(QtCore.QObject):
    #: state_changed(old_state, new_state, new_state_info=None)
    state_changed = pyqtSignal(int, int, object)

    def __init__(self, mrc_model=None, mrc_config=None, parent=None):
        super(MRC, self).__init__(parent)
        self._model   = None
        self._config  = None
        self._devices = list()
        self.model    = mrc_model
        self.config   = mrc_config

    def get_model(self):
        return self._model() if self._model is not None else None

    def set_model(self, model):
        if self.model is not None:
            self.model.disconnect(self)

        self._model = weakref.ref(model) if model is not None else None

        if self.model is not None:
            self.model.state_changed.connect(self.state_changed)

    def get_config(self):
        return self._config() if self._config is not None else None

    def set_config(self, config):
        self._config = weakref.ref(config) if config is not None else None

    model  = pyqtProperty(object, get_model, set_model)
    config = pyqtProperty(object, get_config, set_config)

class Device(QtCore.QObject):
    #: state_changed(old_state, new_state, new_state_info=None)
    state_changed = pyqtSignal(int, int, object)

    #: parameter_changed(address, old_value, new_value)
    parameter_changed = pyqtSignal(int, int, int)

    def __init__(self, device_model=None, device_config=None,
            device_description=None, parent=None):
        super(Device, self).__init__(parent)
        self._model       = None
        self._config      = None
        self._description = None
        self.model       = device_model
        self.config      = device_config
        self.description = device_description

    def get_model(self):
        return self._model() if self._model is not None else None

    def set_model(self, model):
        if self.model is not None:
            self.model.disconnect(self)

        self._model = weakref.ref(model) if model is not None else None

        if self.model is not None:
            self.model.state_changed.connect(self.state_changed)
            self.model.parameter_changed.connect(self.parameter_changed)

    def get_config(self):
        return self._config() if self._config is not None else None

    def set_config(self, config):
        self._config = weakref.ref(config) if config is not None else None

    def get_description(self):
        return self._description() if self._description is not None else None

    def set_description(self, description):
        self._description = weakref.ref(description) if description is not None else None

    model       = pyqtProperty(object, get_model, set_model)
    config      = pyqtProperty(object, get_config, set_config)
    description = pyqtProperty(DeviceDescription, get_description, set_description)

