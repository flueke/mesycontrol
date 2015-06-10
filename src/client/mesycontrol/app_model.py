#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
import weakref
from qt import QtCore
from qt import pyqtProperty
from qt import pyqtSignal

import basic_model as bm
import util

"""Mesycontrol application model.
These objects merge the hardware and the config models together.

MRC objects are identified by URL, Device objects by (bus, address).
"""

class AppObject(QtCore.QObject):
    config_model_set   = pyqtSignal(object)
    hardware_model_set = pyqtSignal(object)

    def __init__(self, parent=None):
        super(AppObject, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self._hw = self._cfg = None

    def get_hardware_model(self):
        return self._hw

    def set_hardware_model(self, hw):
        self.log.debug("set_hardware_model: self.hw=%s, hw=%s", self.hw, hw)
        if self.hw != hw:
            self._hw = hw
            self.hardware_model_set.emit(self.hw)

    def get_config_model(self):
        return self._cfg

    def set_config_model(self, cfg):
        self.log.debug("set_config_model: self.cfg=%s, cfg=%s", self.cfg, cfg)
        if self.cfg != cfg:
            self._cfg = cfg
            self.config_model_set.emit(self.cfg)

    hw  = pyqtProperty(object, get_hardware_model, set_hardware_model, notify=hardware_model_set)
    cfg = pyqtProperty(object, get_config_model, set_config_model, notify=config_model_set)

class MRCRegistry(AppObject):
    mrc_added   = pyqtSignal(object)
    mrc_removed = pyqtSignal(object)

    def __init__(self, hw_reg, cfg_reg, parent=None):
        super(MRCRegistry, self).__init__(parent)
        self.log  = util.make_logging_source_adapter(__name__, self)
        self.cfg  = cfg_reg
        self.hw   = hw_reg
        self._mrcs = list()

    def add_mrc(self, mrc):
        if self.get_mrc(mrc.url) is not None:
            raise ValueError("MRC '%s' exists" % mrc.url)

        self.log.debug("add_mrc: %s %s", mrc, mrc.url)
        self._mrcs.append(mrc)
        self._mrcs.sort(key=lambda mrc: mrc.url)
        self.mrc_added.emit(mrc)

    def remove_mrc(self, mrc):
        try:
            self._mrcs.remove(mrc)
            self.mrc_removed.emit(mrc)
        except ValueError:
            raise ValueError("No such MRC %s" % mrc)

    def get_mrc(self, url):
        return next((mrc for mrc in self._mrcs if mrc.url == url), None)

    def get_mrcs(self):
        return list(self._mrcs)

    def find_mrc_by_hardware(self, hw_mrc):
        return next((mrc for mrc in self._mrcs if mrc.hw == hw_mrc), None)

    def find_mrc_by_config(self, cfg_mrc):
        return next((mrc for mrc in self._mrcs if mrc.cfg == cfg_mrc), None)

    def __iter__(self):
        return iter(self._mrcs)

    mrcs = pyqtProperty(list, get_mrcs)

class MRC(AppObject):
    device_added    = pyqtSignal(object)
    device_removed  = pyqtSignal(object)

    def __init__(self, url, parent=None):
        super(MRC, self).__init__(parent)
        self.log  = util.make_logging_source_adapter(__name__, self)
        self._url = str(url)
        self._devices = list()

    def add_device(self, device):
        if self.get_device(device.bus, device.address) is not None:
            raise ValueError("Device at (%d, %d) exists", device.bus, device.address)

        self.log.debug("add_device: %s", device)

        self._devices.append(device)
        self._devices.sort(key=lambda device: (device.bus, device.address))
        device.mrc = self
        self.device_added.emit(device)
        return True

    def remove_device(self, device):
        try:
            self._devices.remove(device)
            device.mrc = None
            self.log.debug("remove_device: %s", device)
            self.device_removed.emit(device)
            return True
        except ValueError:
            raise ValueError("No Device %s" % device)

    def get_device(self, bus, address):
        compare = lambda d: (d.bus, d.address) == (bus, address)
        return next((dev for dev in self._devices if compare(dev)), None)
    
    def get_devices(self, bus=None):
        if bus is None:
            return list(self._devices)
        return [d for d in self._devices if d.bus == bus]

    def get_url(self):
        return self._url

    def __iter__(self):
        return iter(self._devices)

    url     = pyqtProperty(str, get_url)
    devices = pyqtProperty(list, get_devices)

class Device(AppObject):
    mrc_changed = pyqtSignal(object)

    def __init__(self, bus, address, mrc=None, parent=None):
        super(Device, self).__init__(parent)

        self.bus        = int(bus)
        self.address    = int(address)
        self._mrc       = None
        self.mrc        = mrc

        if self.bus not in bm.BUS_RANGE:
            raise ValueError("Bus out of range")

        if self.address not in bm.DEV_RANGE:
            raise ValueError("Device address out of range")

    def get_mrc(self):
        return None if self._mrc is None else self._mrc()

    def set_mrc(self, mrc):
        if self.mrc != mrc:
            self._mrc = None if mrc is None else weakref.ref(mrc)
            self.mrc_changed.emit(self.mrc)
            return True

        return False

    mrc = pyqtProperty(object, get_mrc, set_mrc, notify=mrc_changed)

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
        mrc.url_changed.connect(partial(self._hw_mrc_url_changed, mrc))

    def _hw_mrc_removed(self, mrc):
        self.log.debug("_hw_mrc_removed: %s", mrc)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_mrc.hw = None
        for device in mrc.get_devices():
            self._hw_mrc_device_removed(mrc, device)
        if app_mrc.cfg is None:
            self.registry.remove_mrc(app_mrc)

    def _hw_mrc_url_changed(self, mrc, url):
        self.log.debug("_hw_mrc_url_changed: mrc=%s, url=%s", mrc, url)

        app_mrc = self.registry.find_mrc_by_hardware(mrc)

        for hw_device in app_mrc.hw:
            app_mrc.hw.remove_device(hw_device)

        app_mrc.hw = None

        if app_mrc.cfg is None:
            self.registry.remove_mrc(app_mrc)

        app_mrc = self.registry.get_mrc(url)

        if app_mrc is None:
            app_mrc = MRC(mrc.url)
            self.registry.add_mrc(app_mrc)
        app_mrc.hw = mrc

    def _hw_mrc_device_added(self, mrc, device):
        self.log.debug("_hw_mrc_device_added: mrc=%s, device=%s", mrc, device)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_device = app_mrc.get_device(device.bus, device.address)
        if app_device is None:
            app_device = Device(device.bus, device.address)
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
        mrc.url_changed.connect(partial(self._config_mrc_url_changed, mrc))

    def _config_mrc_removed(self, mrc):
        self.log.debug("_config_mrc_removed: %s", mrc)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_mrc.cfg = None
        for device in mrc.get_devices():
            self._config_mrc_device_removed(mrc, device)
        if app_mrc.hw is None:
            self.registry.remove_mrc(app_mrc)

    def _config_mrc_url_changed(self, mrc, url):
        self.log.debug("_hw_mrc_url_changed: mrc=%s, url=%s", mrc, url)

        app_mrc = self.registry.find_mrc_by_config(mrc)

        for cfg_device in app_mrc.cfg:
            app_mrc.cfg.remove_device(cfg_device)

        app_mrc.cfg = None

        if app_mrc.hw is None:
            self.registry.remove_mrc(app_mrc)

        app_mrc = self.registry.get_mrc(url)

        if app_mrc is None:
            app_mrc = MRC(mrc.url)
            self.registry.add_mrc(app_mrc)
        app_mrc.cfg = mrc

    def _config_mrc_device_added(self, mrc, device):
        self.log.debug("_config_mrc_device_added: mrc=%s, device=%s", mrc, device)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_device = app_mrc.get_device(device.bus, device.address)
        if app_device is None:
            app_device = Device(device.bus, device.address)
            app_mrc.add_device(app_device)
        app_device.cfg = device

    def _config_mrc_device_removed(self, mrc, device):
        self.log.debug("_config_mrc_device_removed: mrc=%s, device=%s", mrc, device)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_device = app_mrc.get_device(device.bus, device.address)
        app_device.cfg = None
        if app_device.hw is None:
            app_mrc.remove_device(app_device)
