#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
import weakref

from device_description import DeviceDescription

class Device(QtCore.QObject):
    changed = pyqtSignal()

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
        is_changed = self.model != model

        if self.model is not None:
            self.model.disconnect(self)

        self._model = weakref.ref(model) if model is not None else None

        if self.model is not None:
            self.model.state_changed.connect(self.changed)
            self.model.idc_changed.connect(self.changed)
            self.model.rc_changed.connect(self.changed)
            self.model.parameter_changed.connect(self.changed)
            self.model.mirror_parameter_changed.connect(self.changed)
            self.model.memory_reset.connect(self.changed)
            self.model.mirror_reset.connect(self.changed)

        if is_changed:
            self.changed.emit()

    def get_config(self):
        return self._config() if self._config is not None else None

    def set_config(self, config):
        is_changed = self.config != config

        if self.config is not None:
            self.config.disconnect(self)

        self._config = weakref.ref(config) if config is not None else None

        if self.config is not None:
            self.config.changed.connect(self.changed)

        if is_changed:
            self.changed.emit()

    def get_description(self):
        return self._description() if self._description is not None else None

    def set_description(self, description):
        self._description = weakref.ref(description) if description is not None else None

    model       = pyqtProperty(object, get_model, set_model)
    config      = pyqtProperty(object, get_config, set_config)
    description = pyqtProperty(DeviceDescription, get_description, set_description)

class MRC(QtCore.QObject):
    #: state_changed(old_state, new_state, new_state_info=None)
    state_changed = pyqtSignal(int, int, object)

    device_added  = pyqtSignal(Device)

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
            self.model.device_added.connect(self._on_device_added)

    def get_config(self):
        return self._config() if self._config is not None else None

    def set_config(self, config):
        self._config = weakref.ref(config) if config is not None else None

    def get_devices(self):
        return list(self._devices)

    def _on_device_added(self, device_model):
        device = Device(device_model)
        self._devices.append(device)
        self.device_added.emit(device)

    model  = pyqtProperty(object, get_model, set_model)
    config = pyqtProperty(object, get_config, set_config)

    devices = pyqtProperty(list, get_devices)
