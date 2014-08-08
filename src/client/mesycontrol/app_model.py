#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
import weakref

from device_description import DeviceDescription
import application_registry

class Device(QtCore.QObject):
    changed                         = pyqtSignal()          #: generic "something changed"
    config_set                      = pyqtSignal(object)    #: a new config object has been set
    model_set                       = pyqtSignal(object)    #: a new model object has been set

    # hw model related:
    idc_changed                     = pyqtSignal(int)
    rc_changed                      = pyqtSignal(bool)
    state_changed                   = pyqtSignal(int, int, object)
    address_conflict_changed        = pyqtSignal(bool)
    parameter_changed               = pyqtSignal(int, int, int)
    mirror_parameter_changed        = pyqtSignal(int, int, int)
    write_access_changed            = pyqtSignal(bool)
    silence_changed                 = pyqtSignal(bool)

    # config related:
    name_changed                    = pyqtSignal(object)
    config_idc_changed              = pyqtSignal(int)
    config_rc_changed               = pyqtSignal(bool)
    config_parameter_changed        = pyqtSignal(int, int, int)
    config_mirror_parameter_changed = pyqtSignal(int, int, int)

    # controller related
    request_queue_size_changed      = pyqtSignal(int)
    request_sent                    = pyqtSignal(object, object)          #: request_id, request
    request_canceled                = pyqtSignal(object, object)          #: request_id, request
    request_completed               = pyqtSignal(object, object, object)  #: request_id, request, response

    def __init__(self, device_model=None, device_config=None,
            device_description=None, parent=None):
        super(Device, self).__init__(parent)

        self.config_set.connect(self.changed)
        self.model_set.connect(self.changed)
        self.name_changed.connect(self.changed)
        self.idc_changed.connect(self.changed)
        self.rc_changed.connect(self.changed)
        self.state_changed.connect(self.changed)
        self.address_conflict_changed.connect(self.changed)
        self.parameter_changed.connect(self.changed)
        self.config_parameter_changed.connect(self.changed)
        self.mirror_parameter_changed.connect(self.changed)

        self._model       = None
        self._config      = None
        self._description = None
        self._name        = None

        self.model       = device_model
        self.config      = device_config
        self.description = device_description

    def __str__(self):
        if self.name is not None:
            return self.name

        if self.description is not None:
            return "%s@(%d,%d)" % (self.description.name, self.bus, self.address)
        else:
            return "Device(idc=%d)@(%d,%d)" % (self.idc, self.bus, self.address)

    def get_model(self):
        return self._model() if self._model is not None else None

    def set_model(self, model):
        is_changed = self.model != model

        # FIXME: disconnect model here
        #if self.model is not None:
        #    self.model.disconnect(self)

        self._model = weakref.ref(model) if model is not None else None

        if self.model is not None:
            self.model.state_changed.connect(self.state_changed)
            self.model.idc_changed.connect(self.idc_changed)
            self.model.rc_changed.connect(self.rc_changed)
            self.model.address_conflict_changed.connect(self.address_conflict_changed)
            self.model.parameter_changed.connect(self.parameter_changed)
            self.model.mirror_parameter_changed.connect(self.mirror_parameter_changed)

            self.model.controller.write_access_changed.connect(self.write_access_changed)
            self.model.controller.silence_changed.connect(self.silence_changed)
            self.model.controller.request_queue_size_changed.connect(self.request_queue_size_changed)
            self.model.controller.request_sent.connect(self.request_sent)
            self.model.controller.request_canceled.connect(self.request_canceled)
            self.model.controller.request_completed.connect(self.request_completed)

        if is_changed:
            self.model_set.emit(self.model)

    def get_config(self):
        #return self._config() if self._config is not None else None
        return self._config

    def set_config(self, config):
        if self.config is not None:
            self.config.changed.disconnect(self.changed)
            self.config.parameter_changed.disconnect(self.config_parameter_changed)

        #self._config = weakref.ref(config) if config is not None else None
        self._config = config

        if self.config is not None:
            self.config.changed.connect(self.changed)
            #self.config.bus_changed.connect(self.config_bus_changed)
            #self.config.address_changed.connect(self.config_address_changed)
            #self.config.idc_changed.connect(self.config_idc_changed)
            #self.config.rc_changed.connect(self.config_rc_changed)
            self.config.parameter_changed.connect(self.config_parameter_changed)
            self.name = self.config.name

        self.config_set.emit(self.config)

    def get_description(self):
        return self._description() if self._description is not None else None

    def set_description(self, description):
        self._description = weakref.ref(description) if description is not None else None

    def set_name(self, name):
        self._name = str(name) if name is not None else None
        self.name_changed.emit(self.name)

    def get_name(self):
        return self._name

    def get_bus(self):
        return self.model.bus

    def get_address(self):
        return self.model.address

    def get_idc(self):
        return self.model.idc

    def get_rc(self):
        return self.model.rc

    def set_rc(self, on_off, response_handler=None):
        return self.model.controller.set_rc(on_off, response_handler)

    def read_parameter(self, address, response_handler=None):
        return self.model.controller.read_parameter(address, response_handler)

    def get_parameter(self, address):
        return self.model.get_parameter(address)

    def has_parameter(self, address):
        return self.model.has_parameter(address)

    def set_parameter(self, address, value, response_handler=None):
        return self.model.controller.set_parameter(address, value, response_handler)

    def get_config_parameter(self, address):
        return self.config.get_parameter(address)

    def has_config_parameter(self, address):
        return self.config.contains_parameter(address)

    def has_all_parameters(self):
        return all(map(self.has_parameter, range(256)))

    def get_memory(self):
        return self.model.get_memory()

    def get_request_queue_size(self):
        """Returns the size of this devices pending request queue."""
        return self.model.controller.get_request_queue_size()

    def cancel_all_requests(self):
        """Cancels all pending requests."""
        self.model.controller.cancel_all_requests()

    def has_write_access(self):
        return self.model.controller.has_write_access()

    def acquire_write_access(self, force=False, response_handler=None):
        return self.model.controller.set_write_access(True, force, response_handler)

    def release_write_access(self, response_handler=None):
        return self.model.controller.set_write_access(False, response_handler=response_handler)

    def is_silenced(self):
        return self.model.controller.is_silenced()

    def set_silenced(self, on_off, response_handler=None):
        return self.model.controller.set_silenced(on_off)

    def is_connected(self):
        return self.model.is_connected()

    model       = pyqtProperty(object, get_model, set_model)
    config      = pyqtProperty(object, get_config, set_config)
    description = pyqtProperty(DeviceDescription, get_description, set_description)

    name    = pyqtProperty(str, get_name, set_name, notify=name_changed)
    bus     = pyqtProperty(int, get_bus)
    address = pyqtProperty(int, get_address)
    idc     = pyqtProperty(int, get_idc, notify=idc_changed)
    rc      = pyqtProperty(bool, get_rc, set_rc, notify=rc_changed)


class MRC(QtCore.QObject):
    #: state_changed(old_state, new_state, new_state_info=None)
    state_changed                   = pyqtSignal(int, int, object)
    device_added                    = pyqtSignal(Device)
    write_access_changed            = pyqtSignal(bool)
    silence_changed                 = pyqtSignal(bool)
    request_queue_size_changed      = pyqtSignal(int)
    request_sent                    = pyqtSignal(object, object)          #: request_id, request
    request_canceled                = pyqtSignal(object, object)          #: request_id, request
    request_completed               = pyqtSignal(object, object, object)  #: request_id, request, response

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
            self.model.controller.write_access_changed.connect(self.write_access_changed)
            self.model.controller.silence_changed.connect(self.silence_changed)
            self.model.controller.request_queue_size_changed.connect(self.request_queue_size_changed)
            self.model.controller.request_sent.connect(self.request_sent)
            self.model.controller.request_canceled.connect(self.request_canceled)
            self.model.controller.request_completed.connect(self.request_completed)

    def get_config(self):
        return self._config() if self._config is not None else None

    def set_config(self, config):
        self._config = weakref.ref(config) if config is not None else None

    def get_devices(self, bus=None):
        if bus == None:
            return list(self._devices)
        return filter(lambda d: d.bus == bus, self._devices)

    def get_device(self, bus, address):
        f = lambda d: d.bus == bus and d.address == address
        try:
            return filter(f, self._devices)[0]
        except IndexError:
            raise KeyError("No such device bus=%d, address=%d" % (bus, address))

    def is_connected(self):
        return self.model.is_connected()

    def connect(self):
        return self.model.controller.connect()

    def disconnect(self):
        return self.model.controller.disconnect()

    def get_state(self):
        return self.model.state

    def get_request_queue_size(self):
        return self.model.controller.get_request_queue_size()

    def has_write_access(self):
        return self.model.controller.has_write_access()

    def acquire_write_access(self, force=False, response_handler=None):
        return self.model.controller.set_write_access(True, force, response_handler)

    def release_write_access(self, response_handler=None):
        return self.model.controller.set_write_access(False, response_handler=response_handler)

    def is_silenced(self):
        return self.model.controller.is_silenced()

    def set_silenced(self, on_off, response_handler=None):
        return self.model.controller.set_silenced(on_off, response_handler)

    def scanbus(self, bus, response_handler=None):
        return self.model.controller.scanbus(bus, response_handler)

    def _on_device_added(self, device_model):
        description = application_registry.instance.get_device_description_by_idc(device_model.idc)

        device = Device(device_model=device_model, device_description=description)
        self._devices.append(device)
        self.device_added.emit(device)

    def __str__(self):
        if self.config is None:
            return "MRC-1@%s" % (self.model.get_connection_info(),)

    model        = pyqtProperty(object, get_model, set_model)
    config       = pyqtProperty(object, get_config, set_config)
    devices      = pyqtProperty(list, get_devices)
    state        = pyqtProperty(int, get_state)
