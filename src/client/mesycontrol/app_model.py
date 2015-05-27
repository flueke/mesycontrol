#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
from functools import wraps
from qt import pyqtProperty
from qt import pyqtSignal

import basic_model as bm
import util

# FIXME: The app model classes should not inherit the basic model classes.
# FIXME: Reason: methods like Device.read_parameter() are not well defined for
# FIXME: the app model. Also an app model device does not neccessarily have a single
# FIXME: IDC but one for the hardware and one for the config.
# Parameters for app model classes:
# MRC: url
# Device: bus address

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

def modifies_extensions(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        ret = f(self, *args, **kwargs)
        for name, value in self.get_extensions():
            self.config.set_extension(name, value)
        return ret
    return wrapper

class MRCRegistry(bm.MRCRegistry):
    config_model_set   = pyqtSignal(object)
    hardware_model_set = pyqtSignal(object)

    def __init__(self, hw_reg, cfg_reg, parent=None):
        super(MRCRegistry, self).__init__(parent)
        self.log  = util.make_logging_source_adapter(__name__, self)
        self.cfg  = cfg_reg
        self.hw   = hw_reg

    def get_hardware_model(self):
        return self._hw

    def set_hardware_model(self, hw):
        self.log.debug("%s.set_hardware_model %s", self, hw)
        self._hw = hw
        self.hardware_model_set.emit(self.hw)

    def get_config_model(self):
        return self._cfg

    def set_config_model(self, cfg):
        self.log.debug("%s.set_config_model %s", self, cfg)
        self._cfg = cfg
        self.config_model_set.emit(self.cfg)

    hw  = pyqtProperty(object, get_hardware_model, set_hardware_model, notify=hardware_model_set)
    cfg = pyqtProperty(object, get_config_model, set_config_model, notify=config_model_set)


class MRC(bm.MRC):
    config_model_set   = pyqtSignal(object)
    hardware_model_set = pyqtSignal(object)

    def __init__(self, url, parent=None):
        super(MRC, self).__init__(url, parent)
        self.log  = util.make_logging_source_adapter(__name__, self)
        self._cfg = None
        self._hw  = None

    def get_hardware_model(self):
        return self._hw

    def set_hardware_model(self, hw):
        self.log.debug("%s.set_hardware_model %s", self, hw)
        self._hw = hw
        self.hardware_model_set.emit(self.hw)

    def get_config_model(self):
        return self._cfg

    def set_config_model(self, cfg):
        self.log.debug("%s.set_config_model %s", self, cfg)
        self._cfg = cfg
        self.config_model_set.emit(self.cfg)

    hw  = pyqtProperty(object, get_hardware_model, set_hardware_model, notify=hardware_model_set)
    cfg = pyqtProperty(object, get_config_model, set_config_model, notify=config_model_set)

class Device(bm.Device):
    config_model_set   = pyqtSignal(object)
    hardware_model_set = pyqtSignal(object)

    def __init__(self, bus, address, idc, parent=None):
        super(Device, self).__init__(bus, address, idc, parent)
        self.log  = util.make_logging_source_adapter(__name__, self)
        self._cfg = None
        self._hw  = None

    def get_hardware_model(self):
        return self._hw

    def set_hardware_model(self, hw):
        self.log.debug("%s.set_hardware_model %s", self, hw)
        self._hw = hw
        self.hardware_model_set.emit(self.hw)

    def get_config_model(self):
        return self._cfg

    def set_config_model(self, cfg):
        self.log.debug("%s.set_config_model %s", self, cfg)
        self._cfg = cfg
        self.config_model_set.emit(self.cfg)

    hw  = pyqtProperty(object, get_hardware_model, set_hardware_model, notify=hardware_model_set)
    cfg = pyqtProperty(object, get_config_model, set_config_model, notify=config_model_set)

class Director(object):
    def __init__(self, hw_registry, cfg_registry):
        self.registry = MRCRegistry(hw_registry, cfg_registry)
        self.log      = util.make_logging_source_adapter(__name__, self)

        for mrc in hw_registry.mrcs:
            self._hw_mrc_added(mrc)

        for mrc in cfg_registry.mrcs:
            self._config_mrc_added(mrc)

        hw_registry.mrc_added.connect(self._hw_mrc_added)
        hw_registry.mrc_removed.connect(self._hw_mrc_removed)

        cfg_registry.mrc_added.connect(self._config_mrc_added)
        cfg_registry.mrc_removed.connect(self._config_mrc_removed)

    def _hw_mrc_added(self, mrc):
        self.log.debug("_hw_mrc_added: %s", mrc)
        app_mrc = self.registry.get_mrc(mrc.url)
        if app_mrc is None:
            app_mrc = MRC(mrc.url)
            self.registry.add_mrc(app_mrc)
        app_mrc.hw = mrc
        for device in mrc.get_devices():
            self._hw_mrc_device_added(mrc, device)
        mrc.device_added.connect(partial(self._hw_mrc_device_added, mrc))
        mrc.device_removed.connect(partial(self._hw_mrc_device_removed, mrc))

    def _hw_mrc_removed(self, mrc):
        self.log.debug("_hw_mrc_removed: %s", mrc)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_mrc.hw = None
        for device in mrc.get_devices():
            self._hw_mrc_device_removed(mrc, device)
        if app_mrc.cfg is None:
            self.registry.remove_mrc(app_mrc)

    def _hw_mrc_device_added(self, mrc, device):
        self.log.debug("_hw_mrc_device_added: mrc=%s, device=%s", mrc, device)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_device = app_mrc.get_device(device.bus, device.address)
        if app_device is None:
            app_device = Device(device.bus, device.address, device.idc)
            app_mrc.add_device(app_device)
        app_device.hw = device

    def _hw_mrc_device_removed(self, mrc, device):
        self.log.debug("_hw_mrc_device_removed: mrc=%s, device=%s", mrc, device)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_device = app_mrc.get_device(device.bus, device.address)
        app_device.hw = None
        if app_device.cfg is None:
            app_mrc.remove_device(app_device)

    def _config_mrc_added(self, mrc):
        self.log.debug("_config_mrc_added: %s", mrc)
        app_mrc = self.registry.get_mrc(mrc.url)
        if app_mrc is None:
            app_mrc = MRC(mrc.url)
            self.log.debug("_config_mrc_added: created %s", app_mrc)
            self.registry.add_mrc(app_mrc)
        app_mrc.cfg = mrc
        for device in mrc.get_devices():
            self._config_mrc_device_added(mrc, device)
        mrc.device_added.connect(partial(self._config_mrc_device_added, mrc))
        mrc.device_removed.connect(partial(self._config_mrc_device_removed, mrc))

    def _config_mrc_removed(self, mrc):
        self.log.debug("_config_mrc_removed: %s", mrc)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_mrc.cfg = None
        for device in mrc.get_devices():
            self._config_mrc_device_removed(mrc, device)
        if app_mrc.hw is None:
            self.registry.remove_mrc(app_mrc)

    def _config_mrc_device_added(self, mrc, device):
        self.log.debug("_config_mrc_device_added: mrc=%s, device=%s", mrc, device)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_device = app_mrc.get_device(device.bus, device.address)
        if app_device is None:
            app_device = Device(device.bus, device.address, device.idc)
            app_mrc.add_device(app_device)
        app_device.cfg = device

    def _config_mrc_device_removed(self, mrc, device):
        self.log.debug("_config_mrc_device_removed: mrc=%s, device=%s", mrc, device)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_device = app_mrc.get_device(device.bus, device.address)
        app_device.cfg = None
        if app_device.hw is None:
            app_mrc.remove_device(app_device)
