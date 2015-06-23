#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

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
    hardware_set = pyqtSignal(object, object, object) #: self, old, new
    config_set   = pyqtSignal(object, object, object) #: self, old, new

    def __init__(self, hardware=None, config=None, parent=None):
        super(AppObject, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self._hw = self._cfg = None
        self.hw  = hardware
        self.cfg = config

    def get_hardware(self):
        return self._hw

    def set_hardware(self, hw):
        self.log.debug("set_hardware: self.hw=%s, hw=%s", self.hw, hw)
        if self.hw != hw:
            old = self.hw
            self._hw = hw
            self.hardware_set.emit(self, old, self.hw)

    def get_config(self):
        return self._cfg

    def set_config(self, cfg):
        self.log.debug("set_config: self.cfg=%s, cfg=%s", self.cfg, cfg)
        if self.cfg != cfg:
            old = self.cfg
            self._cfg = cfg
            self.config_set.emit(self, old, self.cfg)

    hw  = pyqtProperty(object, get_hardware, set_hardware, notify=hardware_set)
    cfg = pyqtProperty(object, get_config, set_config, notify=config_set)

    has_hw  = property(lambda self: self.hw is not None)
    has_cfg = property(lambda self: self.cfg is not None)

class MRCRegistry(AppObject):
    mrc_added   = pyqtSignal(object)
    mrc_about_to_be_removed = pyqtSignal(object)
    mrc_removed = pyqtSignal(object)

    def __init__(self, hw_reg, cfg_reg, parent=None):
        super(MRCRegistry, self).__init__(hardware=hw_reg, config=cfg_reg, parent=parent)
        self.log  = util.make_logging_source_adapter(__name__, self)
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
            if mrc not in self._mrcs:
                raise ValueError()
            self.mrc_about_to_be_removed.emit(mrc)
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

    def __str__(self):
        return "%s.MRCRegistry(id=%s, hw=%s, cfg=%s)" % (
                __name__, hex(id(self)), self.hw, self.cfg)

    setup = pyqtProperty(object,
            fget=lambda s: s.cfg,
            fset=lambda s, v: s.set_config(v))
    mrcs  = pyqtProperty(list, get_mrcs)

class MRC(AppObject):
    device_added    = pyqtSignal(object)
    device_about_to_be_removed = pyqtSignal(object)
    device_removed  = pyqtSignal(object)

    def __init__(self, url, hw_mrc=None, cfg_mrc=None, parent=None):
        super(MRC, self).__init__(hardware=hw_mrc, config=cfg_mrc, parent=parent)
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
            if device not in self._devices:
                raise ValueError()
            self.device_about_to_be_removed.emit(device)
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

    def get_display_url(self):
        return util.display_url(self.url)

    def __iter__(self):
        return iter(self._devices)

    def __str__(self):
        return "%s.MRC(id=%s, url=%s, hw=%s, cfg=%s)" % (
                __name__, hex(id(self)), self.url, self.hw, self.cfg)

    url     = pyqtProperty(str, get_url)
    devices = pyqtProperty(list, get_devices)

class Device(AppObject):
    mrc_changed = pyqtSignal(object)
    idc_conflict_changed = pyqtSignal(bool)

    def __init__(self, bus, address, mrc=None, hw_device=None, cfg_device=None, profile=None, parent=None):
        self.bus        = int(bus)
        self.address    = int(address)

        if self.bus not in bm.BUS_RANGE:
            raise ValueError("Bus out of range")

        if self.address not in bm.DEV_RANGE:
            raise ValueError("Device address out of range")

        super(Device, self).__init__(hardware=hw_device, config=cfg_device, parent=parent)

        self._mrc       = None
        self.mrc        = mrc
        self.profile    = profile
        self._idc_conflict = False

        self.hardware_set.connect(self._update_idc_conflict)
        self.config_set.connect(self._update_idc_conflict)
        self._update_idc_conflict()

    def get_mrc(self):
        return None if self._mrc is None else self._mrc()

    def set_mrc(self, mrc):
        if self.mrc != mrc:
            self._mrc = None if mrc is None else weakref.ref(mrc)
            self.mrc_changed.emit(self.mrc)
            return True

        return False

    def __str__(self):
        return "%s.Device(id=%s, b=%d, a=%d, mrc=%s, hw=%s, cfg=%s)" % (
                __name__, hex(id(self)), self.bus, self.address, self.mrc, self.hw, self.cfg)

    def _update_idc_conflict(self):
        conflict = self.has_hw and self.has_cfg and self.hw.idc != self.cfg.idc
        if conflict != self._idc_conflict:
            self._idc_conflict = conflict
            self.idc_conflict_changed.emit(self.idc_conflict)

    def has_idc_conflict(self):
        return self._idc_conflict

    mrc = pyqtProperty(object, get_mrc, set_mrc, notify=mrc_changed)
    idc_conflict = pyqtProperty(bool, has_idc_conflict, notify=idc_conflict_changed)

class Director(object):
    def __init__(self, app_registry, device_registry):
        self.log                = util.make_logging_source_adapter(__name__, self)
        self.registry           = app_registry
        self.device_registry    = device_registry

        self._hw_registry_set(app_registry, None, app_registry.hw)
        self._cfg_registry_set(app_registry, None, app_registry.cfg)

        app_registry.hardware_set.connect(self._hw_registry_set)
        app_registry.config_set.connect(self._cfg_registry_set)

    def _make_device(self, bus, address, hw_device=None, cfg_device=None):
        # hardware idc has precedence for profile selection
        idc = hw_device.idc if hw_device is not None else cfg_device.idc

        profile = self.device_registry.get_profile(idc)

        return Device(bus=bus, address=address, hw_device=hw_device, cfg_device=cfg_device, profile=profile)

    # hardware side
    def _hw_registry_set(self, app_registry, old_hw_reg, new_hw_reg):
        if old_hw_reg is not None:
            old_hw_reg.mrc_added.disconnect(self._hw_mrc_added)
            old_hw_reg.mrc_about_to_be_removed.disconnect(self._hw_mrc_about_to_be_removed)

            for mrc in old_hw_reg.mrcs:
                self._hw_mrc_about_to_be_removed(mrc)

        if new_hw_reg is not None:
            new_hw_reg.mrc_added.connect(self._hw_mrc_added)
            new_hw_reg.mrc_about_to_be_removed.connect(self._hw_mrc_about_to_be_removed)

            for mrc in new_hw_reg.mrcs:
                self._hw_mrc_added(mrc)

    def _hw_mrc_added(self, mrc):
        self.log.debug("_hw_mrc_added: %s", mrc)

        # Search by URL here instead of using find_mrc_by_hardware() as there is
        # no app_model.MRC pointing to newly added MRC hardware yet.
        app_mrc = self.registry.get_mrc(mrc.url)

        if app_mrc is None:
            app_mrc = MRC(mrc.url, hw_mrc=mrc)
            self.registry.add_mrc(app_mrc)
        else:
            app_mrc.hw = mrc

        for device in mrc.get_devices():
            self._hw_device_added(device)

        mrc.device_added.connect(self._hw_device_added)
        mrc.device_about_to_be_removed.connect(self._hw_device_about_to_be_removed)

    def _hw_mrc_about_to_be_removed(self, mrc):
        self.log.debug("_hw_mrc_about_to_be_removed: %s", mrc)
        for device in mrc.get_devices():
            self._hw_device_about_to_be_removed(device)
        app_mrc = self.registry.find_mrc_by_hardware(mrc)
        app_mrc.hw = None
        if app_mrc.cfg is None:
            self.registry.remove_mrc(app_mrc)

    def _hw_device_added(self, device):
        self.log.debug("_hw_device_added: device=%s", device)
        app_mrc = self.registry.find_mrc_by_hardware(device.mrc)
        app_device = app_mrc.get_device(device.bus, device.address)
        if app_device is None:
            app_device = self._make_device(bus=device.bus, address=device.address, hw_device=device)
            app_mrc.add_device(app_device)
        else:
            app_device.hw = device

    def _hw_device_about_to_be_removed(self, device):
        self.log.debug("_hw_device_about_to_be_removed: device=%s", device)
        app_mrc = self.registry.find_mrc_by_hardware(device.mrc)
        app_device = app_mrc.get_device(device.bus, device.address)
        app_device.hw = None
        if app_device.cfg is None:
            app_mrc.remove_device(app_device)

    # config side
    def _cfg_registry_set(self, app_registry, old_cfg_reg, new_cfg_reg):
        if old_cfg_reg is not None:
            old_cfg_reg.mrc_added.disconnect(self._cfg_mrc_added)
            old_cfg_reg.mrc_about_to_be_removed.disconnect(self._cfg_mrc_about_to_be_removed)

            for mrc in old_cfg_reg.mrcs:
                self._cfg_mrc_about_to_be_removed(mrc)

        if new_cfg_reg is not None:
            new_cfg_reg.mrc_added.connect(self._cfg_mrc_added)
            new_cfg_reg.mrc_about_to_be_removed.connect(self._cfg_mrc_about_to_be_removed)

            for mrc in new_cfg_reg.mrcs:
                self._cfg_mrc_added(mrc)

    def _cfg_mrc_added(self, mrc):
        self.log.debug("_cfg_mrc_added: %s", mrc)

        # Search by URL here instead of using find_mrc_by_config() as there is
        # no app_model.MRC pointing to newly added MRC config yet.
        app_mrc = self.registry.get_mrc(mrc.url)

        if app_mrc is None:
            app_mrc = MRC(mrc.url, cfg_mrc=mrc)
            self.registry.add_mrc(app_mrc)
        else:
            app_mrc.cfg = mrc

        for device in mrc.get_devices():
            self._cfg_device_added(device)

        mrc.device_added.connect(self._cfg_device_added)
        mrc.device_about_to_be_removed.connect(self._cfg_device_about_to_be_removed)

    def _cfg_mrc_about_to_be_removed(self, mrc):
        self.log.debug("_cfg_mrc_about_to_be_removed: %s", mrc)
        for device in mrc.get_devices():
            self._cfg_device_about_to_be_removed(device)
        app_mrc = self.registry.find_mrc_by_config(mrc)
        app_mrc.cfg = None
        if app_mrc.hw is None:
            self.registry.remove_mrc(app_mrc)

    def _cfg_device_added(self, device):
        self.log.debug("_cfg_device_added: device=%s", device)
        app_mrc = self.registry.find_mrc_by_config(device.mrc)
        app_device = app_mrc.get_device(device.bus, device.address)
        if app_device is None:
            app_device = self._make_device(bus=device.bus, address=device.address, cfg_device=device)
            app_mrc.add_device(app_device)
        else:
            app_device.cfg = device

    def _cfg_device_about_to_be_removed(self, device):
        self.log.debug("_cfg_device_about_to_be_removed: device=%s", device)
        app_mrc = self.registry.find_mrc_by_config(device.mrc)
        app_device = app_mrc.get_device(device.bus, device.address)
        app_device.cfg = None
        if app_device.hw is None:
            app_mrc.remove_device(app_device)
