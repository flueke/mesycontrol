#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import wraps
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
import logging
import weakref

import config
import hw_model
import util

def device_factory(device_model=None, device_config=None, parent=None):
    import application_registry
    idc = device_model.idc if device_model is not None else device_config.idc
    profile  = application_registry.instance.get_device_profile_by_idc(idc)
    logging.getLogger(__name__).debug("Creating Device(model=%s, config=%s, config.parent=%s)",
            device_model, device_config, device_config.parent())
    return Device(device_model=device_model, device_config=device_config,
            profile=profile, parent=parent)


def model_required(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if not self.has_model():
            raise RuntimeError("No DeviceModel present (Device=%s)" % str(self))
        return f(self, *args, **kwargs)
    return wrapper

def config_required(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if not self.has_config():
            raise RuntimeError("No DeviceConfig present (Device=%s)" % str(self))
        return f(self, *args, **kwargs)
    return wrapper

class Device(QtCore.QObject):
    config_set                      = pyqtSignal(object)    #: a new config object has been set (config.DeviceConfig)
    model_set                       = pyqtSignal(object)    #: a new model object has been set (hw_model.DeviceModel)
    profile_set                     = pyqtSignal(object)    #: a new profile object has been set(device_profile.DeviceProfile)

    # hw model related:
    idc_changed                     = pyqtSignal(int)           #: the hardware idc changed
    rc_changed                      = pyqtSignal(bool)          #: hardware RC flag changed
    connecting                      = pyqtSignal()
    connected                       = pyqtSignal()
    disconnected                    = pyqtSignal()
    ready                           = pyqtSignal(bool)
    address_conflict_changed        = pyqtSignal(bool)
    parameter_changed               = pyqtSignal(int, int, int)
    mirror_parameter_changed        = pyqtSignal(int, int, int)

    # config related:
    name_changed                    = pyqtSignal(str)
    description_changed             = pyqtSignal(str)
    config_idc_changed              = pyqtSignal(int)
    config_bus_changed              = pyqtSignal(int)
    config_address_changed          = pyqtSignal(int)
    config_rc_changed               = pyqtSignal(bool)
    config_parameter_added          = pyqtSignal(int)       #: address
    config_parameter_removed        = pyqtSignal(int)       #: address
    config_parameter_value_changed  = pyqtSignal(int, int)  #: address, value
    config_parameter_alias_changed  = pyqtSignal(int, str)  #: address, alias

    # controller related
    write_access_changed            = pyqtSignal(bool)
    silence_changed                 = pyqtSignal(bool)
    request_queue_size_changed      = pyqtSignal(int)
    request_sent                    = pyqtSignal(object, object)          #: request_id, request
    request_canceled                = pyqtSignal(object, object)          #: request_id, request
    request_completed               = pyqtSignal(object, object, object)  #: request_id, request, response

    def __init__(self, device_model=None, device_config=None, profile=None,
            parent=None):
        super(Device, self).__init__(parent)

        self.log            = util.make_logging_source_adapter(__name__, self)

        self._model         = None
        self._config        = None
        self._profile       = None
        self.model          = device_model
        self.config         = device_config
        self.profile        = profile

    def __str__(self):
        if self.profile is not None:
            if self.is_named():
                return "%s %s@(%d,%d)" % (self.name, self.profile.name, self.bus, self.address)
            return "%s@(%d,%d)" % (self.profile.name, self.bus, self.address)
        else:
            if self.is_named():
                return "%s Device(idc=%d)@(%d,%d)" % (self.name, self.idc, self.bus, self.address)
            return "Device(idc=%d)@(%d,%d)" % (self.idc, self.bus, self.address)

    def has_model(self):
        return self._model is not None and self._model() is not None

    def has_config(self):
        return self._config is not None and self._config() is not None

    def get_model(self):
        return self._model() if self._model is not None else None

    def set_model(self, model):
        if self.model is model:
            return

        if self.model is not None:
            self.model.connecting.disconnect(self.connecting)
            self.model.connected.disconnect(self.connected)
            self.model.disconnected.disconnect(self.disconnected)
            self.model.ready.disconnect(self.ready)
            self.model.idc_changed.disconnect(self.idc_changed)
            self.model.rc_changed.disconnect(self._on_model_rc_changed)
            self.model.address_conflict_changed.disconnect(self.address_conflict_changed)
            self.model.parameter_changed.disconnect(self._on_model_parameter_changed)
            self.model.mirror_parameter_changed.disconnect(self.mirror_parameter_changed)

            self.model.controller.write_access_changed.disconnect(self.write_access_changed)
            self.model.controller.silence_changed.disconnect(self.silence_changed)
            self.model.controller.request_queue_size_changed.disconnect(self.request_queue_size_changed)
            self.model.controller.request_sent.disconnect(self.request_sent)
            self.model.controller.request_canceled.disconnect(self.request_canceled)
            self.model.controller.request_completed.disconnect(self.request_completed)

        self._model = weakref.ref(model) if model is not None else None

        if self.model is not None:
            self.model.connecting.connect(self.connecting)
            self.model.connected.connect(self.connected)
            self.model.disconnected.connect(self.disconnected)
            self.model.ready.connect(self.ready)
            self.model.idc_changed.connect(self.idc_changed)
            self.model.rc_changed.connect(self._on_model_rc_changed)
            self.model.address_conflict_changed.connect(self.address_conflict_changed)
            self.model.parameter_changed.connect(self._on_model_parameter_changed)
            self.model.mirror_parameter_changed.connect(self.mirror_parameter_changed)

            self.model.controller.write_access_changed.connect(self.write_access_changed)
            self.model.controller.silence_changed.connect(self.silence_changed)
            self.model.controller.request_queue_size_changed.connect(self.request_queue_size_changed)
            self.model.controller.request_sent.connect(self.request_sent)
            self.model.controller.request_canceled.connect(self.request_canceled)
            self.model.controller.request_completed.connect(self.request_completed)

        self.model_set.emit(self.model)

    def _on_model_parameter_changed(self, address, old_value, new_value):
        if self.has_config() and not self.config.contains_parameter(address):
            param_profile = self.profile.get_parameter_by_address(address)
            if param_profile is not None and param_profile.should_be_stored():
                self.log.debug("Adding parameter name=%s,addr=%d,val=%d) to config for %s",
                        param_profile.name, address, new_value, self)
                self.config.add_parameter(address, new_value)

        self.parameter_changed.emit(address, old_value, new_value)

    def _on_model_rc_changed(self, on_off):
        if self.has_config():
            self.config.rc = on_off
        self.rc_changed.emit(on_off)

    def get_config(self):
        return self._config() if self._config is not None else None

    def set_config(self, config):
        """Sets a new config object for this device.
        Note: This device will not take ownership of the config object! If you
        want to integrate a new config object into an existing app_model tree
        use the assign_config() method below.
        """
        if self.config is not None:
            self.log.debug("Device.config is not None: %s, parent=%s", self.config, self.config.parent())
            self.config.name_changed.disconnect(self.name_changed)
            self.config.description_changed.disconnect(self.description_changed)
            self.config.idc_changed.disconnect(self.config_idc_changed)
            self.config.bus_changed.disconnect(self.config_bus_changed)
            self.config.address_changed.disconnect(self.config_address_changed)
            self.config.rc_changed.disconnect(self.config_rc_changed)
            self.config.parameter_added.disconnect(self.config_parameter_added)
            self.config.parameter_removed.disconnect(self.config_parameter_removed)
            self.config.parameter_value_changed.disconnect(self.config_parameter_value_changed)
            self.config.parameter_alias_changed.disconnect(self.config_parameter_alias_changed)

        self._config = weakref.ref(config) if config is not None else None

        if self.config is not None:
            self.config.name_changed.connect(self.name_changed)
            self.config.description_changed.connect(self.description_changed)
            self.config.idc_changed.connect(self.config_idc_changed)
            self.config.bus_changed.connect(self.config_bus_changed)
            self.config.address_changed.connect(self.config_address_changed)
            self.config.rc_changed.connect(self.config_rc_changed)
            self.config.parameter_added.connect(self.config_parameter_added)
            self.config.parameter_removed.connect(self.config_parameter_removed)
            self.config.parameter_value_changed.connect(self.config_parameter_value_changed)
            self.config.parameter_alias_changed.connect(self.config_parameter_alias_changed)

        self.config_set.emit(self.config)

    def assign_config(self, config):
        """Assigns a new config object to this device.
        The config object will be integrated into the app_model and config
        trees. Ownership will be taken by the underlying mrc config.
        """
        self.mrc.set_device_config(self, config)

    def get_profile(self):
        return self._profile() if self._profile is not None else None

    def set_profile(self, profile):
        self._profile = weakref.ref(profile) if profile is not None else None
        self.profile_set.emit(self.profile)

    def set_name(self, name):
        self.config.name = name

    def get_name(self):
        return self.config.name if self.config is not None else None

    def is_named(self):
        return self.name is not None and len(self.name)

    def get_bus(self):
        if self.has_model():
            return self.model.bus
        elif self.has_config():
            return self.config.bus

    def get_address(self):
        if self.has_model():
            return self.model.address
        elif self.has_config():
            return self.config.address

    def get_idc(self):
        if self.has_model():
            return self.model.idc
        elif self.has_config():
            return self.config.idc

    def get_rc(self):
        if self.has_model():
            return self.model.rc
        return False

    @model_required
    def set_rc(self, on_off, response_handler=None):
        return self.model.controller.set_rc(on_off, response_handler)

    @model_required
    def read_parameter(self, address, response_handler=None):
        return self.model.controller.read_parameter(address, response_handler)

    @model_required
    def get_parameter(self, address):
        return self.model.get_parameter(address)

    @model_required
    def has_parameter(self, address):
        return self.model.has_parameter(address)

    @model_required
    def set_parameter(self, address, value, response_handler=None):
        return self.model.controller.set_parameter(address, value, response_handler)

    @config_required
    def get_config_parameter(self, address):
        return self.config.get_parameter(address)

    @config_required
    def has_config_parameter(self, address):
        return self.config.contains_parameter(address)

    def has_all_parameters(self):
        return all(map(self.has_parameter, range(256)))

    @model_required
    def get_memory(self):
        return self.model.get_memory()

    def get_request_queue_size(self):
        """Returns the size of this devices pending request queue."""
        if not self.has_model():
            return 0
        return self.model.controller.get_request_queue_size()

    @model_required
    def cancel_all_requests(self):
        """Cancels all pending requests."""
        self.model.controller.cancel_all_requests()

    def has_write_access(self):
        if not self.has_model():
            return False
        return self.model.controller.has_write_access()

    @model_required
    def acquire_write_access(self, force=False, response_handler=None):
        return self.model.controller.set_write_access(True, force, response_handler)

    @model_required
    def release_write_access(self, response_handler=None):
        return self.model.controller.set_write_access(False, response_handler=response_handler)

    def is_silenced(self):
        if not self.has_model():
            return False
        return self.model.controller.is_silenced()

    @model_required
    def set_silenced(self, on_off, response_handler=None):
        return self.model.controller.set_silenced(on_off)

    def is_connected(self):
        if not self.has_model():
            return False
        return self.model.is_connected()

    def is_connecting(self):
        if not self.has_model():
            return False
        return self.model.is_connecting()

    def is_disconnected(self):
        if not self.has_model():
            return True
        return self.model.is_disconnected()

    def is_ready(self):
        if not self.has_model():
            return False
        return self.model.is_ready()

    def get_mrc(self):
        return self.parent()

    model   = pyqtProperty(object, get_model, set_model, notify=model_set)
    config  = pyqtProperty(object, get_config, set_config, notify=config_set)
    profile = pyqtProperty(object, get_profile, set_profile)
    name    = pyqtProperty(str, get_name, set_name, notify=name_changed)
    bus     = pyqtProperty(int, get_bus)
    address = pyqtProperty(int, get_address)
    idc     = pyqtProperty(int, get_idc, notify=idc_changed)
    rc      = pyqtProperty(bool, get_rc, set_rc, notify=rc_changed)
    mrc     = pyqtProperty(object, get_mrc)


class MRC(QtCore.QObject):
    connecting                  = pyqtSignal()
    connected                   = pyqtSignal()
    disconnected                = pyqtSignal(object)    #: error object or None
    ready                       = pyqtSignal(bool)
    device_added                = pyqtSignal(object)    #: Device
    device_removed              = pyqtSignal(object)    #: Device
    write_access_changed        = pyqtSignal(bool)
    silence_changed             = pyqtSignal(bool)
    request_queue_size_changed  = pyqtSignal(int)
    request_sent                = pyqtSignal(object, object)          #: request_id, request
    request_canceled            = pyqtSignal(object, object)          #: request_id, request
    request_completed           = pyqtSignal(object, object, object)  #: request_id, request, response
    name_changed                = pyqtSignal(str)
    description_changed         = pyqtSignal(str)

    def __init__(self, mrc_model=None, mrc_config=None, parent=None):
        super(MRC, self).__init__(parent)
        self.log      = util.make_logging_source_adapter(__name__, self)
        self.log.debug("MRC(model=%s, config=%s)", mrc_model, mrc_config)
        self._model   = None
        self._config  = None
        self._devices = list()
        self.model    = mrc_model
        self.config   = mrc_config

    def set_name(self, name):
        self.config.name = name

    def get_name(self):
        return self.config.name if self.config is not None else None

    def is_named(self):
        return self.name is not None and len(self.name)

    def has_model(self):
        return self._model is not None and self._model() is not None

    def has_config(self):
        return self._config is not None and self._config() is not None

    def get_model(self):
        return self._model() if self._model is not None else None

    def set_model(self, model):
        # FIXME: destroy existing Device instances
        if self.model is not None:
            self.model.connected.disconnect(self.connected)
            self.model.connecting.disconnect(self.connecting)
            self.model.disconnected.disconnect(self.disconnected)
            self.model.ready.disconnect(self.ready)
            self.model.device_added.disconnect(self._on_device_model_added)
            self.model.device_removed.disconnect(self._on_device_model_removed)
            self.model.controller.write_access_changed.disconnect(self.write_access_changed)
            self.model.controller.silence_changed.disconnect(self.silence_changed)
            self.model.controller.request_queue_size_changed.disconnect(self.request_queue_size_changed)
            self.model.controller.request_sent.disconnect(self.request_sent)
            self.model.controller.request_canceled.disconnect(self.request_canceled)
            self.model.controller.request_completed.disconnect(self.request_completed)

        self._model = weakref.ref(model) if model is not None else None

        if self.model is not None:
            for device_model in self.model.get_devices():
                self._on_device_model_added(device_model)

            self.model.connected.connect(self.connected)
            self.model.connecting.connect(self.connecting)
            self.model.disconnected.connect(self.disconnected)
            self.model.ready.connect(self.ready)
            self.model.device_added.connect(self._on_device_model_added)
            self.model.device_removed.connect(self._on_device_model_removed)
            self.model.controller.write_access_changed.connect(self.write_access_changed)
            self.model.controller.silence_changed.connect(self.silence_changed)
            self.model.controller.request_queue_size_changed.connect(self.request_queue_size_changed)
            self.model.controller.request_sent.connect(self.request_sent)
            self.model.controller.request_canceled.connect(self.request_canceled)
            self.model.controller.request_completed.connect(self.request_completed)

    def get_config(self):
        return self._config() if self._config is not None else None

    def set_config(self, config):
        """Set a new MRCConfig object. This also updates the configs of any
        Device objects connected to this MRC."""

        if self.config is not None:
            self.config.device_config_added.disconnect(self._on_device_config_added)
            self.config.device_config_removed.disconnect(self._on_device_config_removed)
            self.config.name_changed.disconnect(self.name_changed)
            self.config.description_changed.disconnect(self.description_changed)

        self._config = weakref.ref(config) if config is not None else None

        if self.config is not None:
            self.config.device_config_added.connect(self._on_device_config_added)
            self.config.device_config_removed.connect(self._on_device_config_removed)
            self.config.name_changed.connect(self.name_changed)
            self.config.description_changed.connect(self.description_changed)

        for bus in range(2):
            for addr in range(16):
                try:
                    device = self.get_device(bus, addr)
                except KeyError:
                    device = None
                try:
                    device_config = (config.get_device_config(bus, addr)
                            if config is not None else None)
                except KeyError:
                    device_config = None

                if device_config is not None:
                    self._on_device_config_added(device_config)
                elif device is not None:
                    device.config = None
                    if device.model is None:
                        self._remove_device(device)

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

    def has_device(self, bus, address):
        f = lambda d: d.bus == bus and d.address == address
        return len(filter(f, self._devices)) > 0

    def is_connected(self):
        return self.model.is_connected()

    def is_connecting(self):
        return self.model.is_connecting()

    def is_disconnected(self):
        return self.model.is_disconnected()

    def is_ready(self):
        return self.model.is_ready()

    def connect(self):
        return self.model.controller.connect()

    def disconnect(self):
        return self.model.controller.disconnect()

    def get_state(self):
        return self.model.state

    def get_request_queue_size(self):
        if not self.has_model():
            return 0
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

    def set_device_config(self, device, config):
        if self.get_device(device.bus, device.address) is not device:
            raise RuntimeError("Given device %s is not a child of %s", device, self)

        self.config.remove_device_config(device.config)
        self.config.add_device_config(config)

    def _on_device_model_added(self, device_model):
        self.log.info("_on_device_model_added: bus=%d, address=%d", device_model.bus, device_model.address)
        # Check if a Device instance matching the models bus and address
        # exists. This is the case if a DeviceConfig for (bus,address) is
        # present but no hw_model.DeviceModel exists.
        try:
            device = self.get_device(bus=device_model.bus, address=device_model.address)
            self.log.info("_on_device_model_added: found existing device %s", device)
            device.set_model(device_model)
            # The device now has a DeviceModel and a DeviceConfig with matching
            # (bus,address) fields.
        except KeyError:
            # No Device present yet. There should be no DeviceConfig for this
            # device either as otherwise a Device instance would've been
            # created at the time the config was set.
            self.log.info("_on_device_model_added: no existing device found. self.config=%s", self.config)
            device_config=None
            if self.config is not None:
                assert not self.config.has_device_config(
                        device_model.bus, device_model.address)
                device_config           = config.DeviceConfig()
                device_config.idc       = device_model.idc
                device_config.bus       = device_model.bus
                device_config.address   = device_model.address
                # add_device_config will trigger _on_device_config_added, which
                # in turn will create a Device instance. This means after the
                # next line the call to get_device() will succeed and return
                # the newly created Device instance.
                self.config.add_device_config(device_config)
                device = self.get_device(device_model.bus, device_model.address)
                device.set_model(device_model)

    def _on_device_model_removed(self, device_model):
        device = self.get_device(bus=device_model.bus, address=device_model.address)
        if device is not None:
            device.set_model(None)
            if device.config is None:
                # Neither model nor config present for this device -> remove it
                self._remove_device(device)

    def _on_device_config_added(self, device_config):
        self.log.info("_on_device_config_added: bus=%d, address=%d", device_config.bus, device_config.address)
        try:
            device = self.get_device(bus=device_config.bus, address=device_config.address)
            self.log.info("_on_device_config_added: found existing device %s", device)
            device.config = device_config
        except KeyError:
            self.log.info("_on_device_config_added: Creating Device(config=%s, idc=%d, bus=%d, address=%d, parent=%s)",
                    device_config, device_config.idc, device_config.bus, device_config.address, self)
            device = device_factory(device_config=device_config, parent=self)
            self._add_device(device)

    def _on_device_config_removed(self, device_config):
        device = self.get_device(bus=device_config.bus, address=device_config.address)
        if device is not None:
            device.config = None
            if device.model is None:
                # Neither model nor config present for this device -> remove it
                self._remove_device(device)

    def _add_device(self, device):
        self.log.info("Adding %s", device)
        if self.has_device(device.bus, device.address):
            raise RuntimeError("Duplicate device added")
        self._devices.append(device)
        device.setParent(self)
        self.device_added.emit(device)
        return device

    def _remove_device(self, device):
        self._devices.remove(device)
        device.setParent(None)
        self.device_removed.emit(device)

    def __str__(self):
        if self.is_named():
            return "%s MRC(%s)" % (self.name, self.model.get_connection_info())
        return "MRC(%s)" % self.model.get_connection_info()
        
    model       = pyqtProperty(hw_model.MRCModel, get_model, set_model)
    config      = pyqtProperty(config.MRCConfig, get_config, set_config)
    devices     = pyqtProperty(list, get_devices)
    name        = pyqtProperty(str, get_name, set_name, notify=name_changed)
