#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial

import basic_model as bm
import hardware_model as hm
import config_model as cm
import util

class MRC(bm.MRC):
    def __init__(self, url, parent=None):
        super(MRC, self).__init__(url, parent)
        self.hw  = None
        self.cfg = None

class Device(bm.Device):
    def __init__(self, bus, address, idc, parent=None):
        super(Device, self).__init__(bus, address, idc, parent)
        self.hw  = None
        self.cfg = None

class Director(object):
    def __init__(self, hw_registry, cfg_registry):
        self.hw_registry    = hw_registry
        self.cfg_registry   = cfg_registry
        self.registry       = bm.MRCRegistry()
        self.log            = util.make_logging_source_adapter(__name__, self)

        for mrc in self.hw_registry.mrcs:
            self._hw_mrc_added(mrc)
            mrc.device_added.connect(partial(self._hw_mrc_device_added, mrc))
            mrc.device_removed.connect(partial(self._hw_mrc_device_removed, mrc))

        for mrc in self.cfg_registry.mrcs:
            self._config_mrc_added(mrc)
            mrc.device_added.connect(partial(self._config_mrc_device_added, mrc))
            mrc.device_removed.connect(partial(self._config_mrc_device_removed, mrc))

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

    def _hw_mrc_removed(self, mrc):
        self.log.debug("_hw_mrc_removed: %s", mrc)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_mrc.hw = None
        for device in mrc.get_devices():
            self._hw_mrc_device_removed(mrc, device)
        if app_mrc.cfg is None:
            self.registry.remove_mrc(app_mrc)

    def _hw_mrc_device_added(self, mrc, device):
        app_mrc = self.registry.get_mrc(mrc.url)
        app_device = app_mrc.get_device(device.bus, device.address)
        if app_device is None:
            app_device = Device(device.bus, device.address, device.idc)
            app_mrc.add_device(app_device)
        app_device.hw = device

    def _hw_mrc_device_removed(self, mrc, device):
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
            self.registry.add_mrc(app_mrc)
        app_mrc.cfg = mrc
        for device in mrc.get_devices():
            self._config_mrc_device_added(mrc, device)

    def _config_mrc_removed(self, mrc):
        self.log.debug("_config_mrc_removed: %s", mrc)
        app_mrc = self.registry.get_mrc(mrc.url)
        app_mrc.cfg = None
        for device in mrc.get_devices():
            self._config_mrc_device_removed(mrc, device)
        if app_mrc.hw is None:
            self.registry.remove_mrc(app_mrc)

    def _config_mrc_device_added(self, mrc, device):
        app_mrc = self.registry.get_mrc(mrc.url)
        app_device = app_mrc.get_device(device.bus, device.address)
        if app_device is None:
            app_device = Device(device.bus, device.address, device.idc)
            app_mrc.add_device(app_device)
        app_device.cfg = device

    def _config_mrc_device_removed(self, mrc, device):
        app_mrc = self.registry.get_mrc(mrc.url)
        app_device = app_mrc.get_device(device.bus, device.address)
        app_device.cfg = None
        if app_device.hw is None:
            app_mrc.remove_device(app_device)
