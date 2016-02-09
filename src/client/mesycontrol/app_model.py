#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2016 mesytec GmbH & Co. KG <info@mesytec.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 
__author__ = 'Florian Lüke'
__email__  = 'florianlueke@gmx.net'

from functools import partial
import weakref

from qt import QtCore
from qt import pyqtProperty
from qt import pyqtSignal

from basic_model import IDCConflict
from model_util import add_mrc_connection
import basic_model as bm
import config_model as cm
import future
import model_util
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
        return "am.MRCRegistry(id=%s, hw=%s, cfg=%s)" % (
                hex(id(self)), self.hw, self.cfg)

    setup = pyqtProperty(object,
            fget=lambda s: s.cfg,
            fset=lambda s, v: s.set_config(v))
    mrcs  = pyqtProperty(list, get_mrcs)

class MRC(AppObject):
    device_added    = pyqtSignal(object)
    device_about_to_be_removed = pyqtSignal(object)
    device_removed  = pyqtSignal(object)
    mrc_registry_changed = pyqtSignal(object)

    def __init__(self, url, mrc_registry=None, hw_mrc=None, cfg_mrc=None, parent=None):
        super(MRC, self).__init__(hardware=hw_mrc, config=cfg_mrc, parent=parent)
        self.log  = util.make_logging_source_adapter(__name__, self)
        self._url = str(url)
        self._devices = list()
        self._mrc_registry = None
        self.mrc_registry = mrc_registry

    def get_mrc_registry(self):
        return self._mrc_registry() if self._mrc_registry is not None else None

    def set_mrc_registry(self, registry):
        if self.mrc_registry != registry:
            self._mrc_registry = None if registry is None else weakref.ref(registry)
            self.mrc_registry_changed.emit(self.mrc_registry)

            return True

        return False

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

    def create_config(self):
        if self.cfg is not None:
            raise RuntimeError("MRC config exists")

        self.mrc_registry.cfg.add_mrc(cm.MRC(self.url))

        return self.cfg

    def __iter__(self):
        return iter(self._devices)

    def __str__(self):
        return "am.MRC(id=%s, url=%s, hw=%s, cfg=%s)" % (
                hex(id(self)), self.url, self.hw, self.cfg)

    url     = pyqtProperty(str, get_url)
    devices = pyqtProperty(list, get_devices)
    mrc_registry = pyqtProperty(object, get_mrc_registry, set_mrc_registry, notify=mrc_registry_changed)

class Device(AppObject):
    mrc_changed             = pyqtSignal(object)

    idc_conflict_changed    = pyqtSignal(bool)
    idc_changed             = pyqtSignal(int)
    hw_idc_changed          = pyqtSignal(int)
    cfg_idc_changed         = pyqtSignal(int)

    module_changed          = pyqtSignal(object)
    hw_module_changed       = pyqtSignal(object)
    cfg_module_changed      = pyqtSignal(object)

    profile_changed         = pyqtSignal(object)
    hw_profile_changed      = pyqtSignal(object)
    cfg_profile_changed     = pyqtSignal(object)

    config_applied_changed  = pyqtSignal(object) # True, False or None with None meaning "unknown"

    hw_parameter_changed    = pyqtSignal(int, object)
    cfg_parameter_changed   = pyqtSignal(int, object)

    hw_extension_changed    = pyqtSignal(str, object)
    cfg_extension_changed   = pyqtSignal(str, object)

    def __init__(self, bus, address, mrc=None, hw_device=None, cfg_device=None,
            hw_module=None, cfg_module=None, parent=None):
        self.bus        = int(bus)
        self.address    = int(address)

        if self.bus not in bm.BUS_RANGE:
            raise ValueError("Bus out of range")

        if self.address not in bm.DEV_RANGE:
            raise ValueError("Device address out of range")

        super(Device, self).__init__(hardware=hw_device, config=cfg_device, parent=parent)

        self.log.debug("am.Device(b=%d, a=%d, hw_device=%s, cfg_device=%s, hw_mod=%s, cfg_mod=%s",
                bus, address, hw_device, cfg_device, hw_module, cfg_module)

        self._mrc               = None
        self._hw_module         = hw_module
        self._cfg_module        = cfg_module
        self._idc_conflict      = False # Set by _update_idc_conflict()
        # _config_applied can take three values: True, False or None with the
        # latter representing the unknown state.
        self._config_applied    = None  # Set by update_config_applied()
        self._config_addresses  = set() # Filled by set_module()

        self.mrc        = mrc
        self._update_config_addresses()

        self.hardware_set.connect(self._on_hardware_set)
        self.config_set.connect(self._on_config_set)
        self.idc_conflict_changed.connect(self.update_config_applied)

        self._update_idc_conflict()
        self._on_hardware_set(self, None, hw_device)
        self._on_config_set(self, None, cfg_device)

    def _on_hardware_set(self, app_model, old_hw, new_hw):
        self._update_idc_conflict()
        self._update_config_addresses()
        self.update_config_applied()

        if old_hw is not None:
            old_hw.parameter_changed.disconnect(self.update_config_applied)
            old_hw.parameter_changed.disconnect(self.hw_parameter_changed)
            old_hw.memory_cleared.disconnect(self.update_config_applied)
            old_hw.idc_changed.disconnect(self._on_hw_idc_changed)
            old_hw.extension_changed.disconnect(self.hw_extension_changed)
            old_hw.extension_changed.disconnect(self.update_config_applied)

        if new_hw is not None:
            new_hw.parameter_changed.connect(self.update_config_applied)
            new_hw.parameter_changed.connect(self.hw_parameter_changed)
            new_hw.memory_cleared.connect(self.update_config_applied)
            new_hw.idc_changed.connect(self._on_hw_idc_changed)
            new_hw.extension_changed.connect(self.hw_extension_changed)
            new_hw.extension_changed.connect(self.update_config_applied)

    def _on_config_set(self, app_model, old_cfg, new_cfg):
        self._update_idc_conflict()
        self._update_config_addresses()
        self.update_config_applied()

        if old_cfg is not None:
            old_cfg.parameter_changed.disconnect(self.update_config_applied)
            old_cfg.parameter_changed.disconnect(self.cfg_parameter_changed)
            old_cfg.memory_cleared.disconnect(self.update_config_applied)
            old_cfg.idc_changed.disconnect(self._on_cfg_idc_changed)
            old_cfg.extension_changed.disconnect(self.cfg_extension_changed)
            old_cfg.extension_changed.disconnect(self.update_config_applied)

        if new_cfg is not None:
            new_cfg.parameter_changed.connect(self.update_config_applied)
            new_cfg.parameter_changed.connect(self.cfg_parameter_changed)
            new_cfg.memory_cleared.connect(self.update_config_applied)
            new_cfg.idc_changed.connect(self._on_cfg_idc_changed)
            new_cfg.extension_changed.connect(self.cfg_extension_changed)
            new_cfg.extension_changed.connect(self.update_config_applied)

    def get_mrc(self):
        return None if self._mrc is None else self._mrc()

    def set_mrc(self, mrc):
        if self.mrc != mrc:
            self._mrc = None if mrc is None else weakref.ref(mrc)
            self.mrc_changed.emit(self.mrc)
            return True

        return False

    # ===== profile ===== #
    def get_idc(self):
        if self.idc_conflict:
            raise IDCConflict()
        return self._hw.idc if self._hw is not None else self._cfg.idc

    def get_hw_idc(self):
        return self._hw.idc if self._hw is not None else None

    def get_cfg_idc(self):
        return self._cfg.idc if self._cfg is not None else None

    def _on_hw_idc_changed(self, idc):
        self.log.debug("%s: _on_hw_idc_changed: idc=%d", self, idc)
        self._update_idc_conflict()
        self.hw_idc_changed.emit(idc)
        if not self.idc_conflict:
            self.idc_changed.emit(idc)

    def _on_cfg_idc_changed(self, idc):
        self.log.debug("%s: _on_cfg_idc_changed: idc=%d", self, idc)
        self._update_idc_conflict()
        self.cfg_idc_changed.emit(idc)
        if not self.idc_conflict:
            self.idc_changed.emit(idc)

    def get_profile(self):
        return self.get_module().profile

    def get_hw_profile(self):
        return self.hw_module.profile

    def get_cfg_profile(self):
        return self.cfg_module.profile

    # ===== module ===== #
    def get_module(self):
        if self.idc_conflict:
            raise IDCConflict()
        return self._hw_module if self._hw_module is not None else self._cfg_module

    def get_hw_module(self):
        return self._hw_module

    def get_cfg_module(self):
        return self._cfg_module

    def set_module(self, module):
        self.log.debug("set_module: module=%s", module)

        if self.idc_conflict:
            raise IDCConflict()

        if module.idc != self.idc:
            raise IDCConflict()

        self.set_hw_module(module)
        self.set_cfg_module(module)

        self.module_changed.emit(self.module)
        self.profile_changed.emit(self.profile)
        return True

    def set_hw_module(self, module):
        if self.has_hw and self.hw_idc != module.idc:
            raise IDCConflict()

        self.log.debug("%s: set_hw_module: module=%s", self, module)

        if self._hw_module != module:
            self._hw_module = module
            self.hw_module_changed.emit(module)
            self.hw_profile_changed.emit(module.profile)
            self._update_config_addresses()

    def set_cfg_module(self, module):
        if self.has_cfg and self.cfg_idc != module.idc:
            raise IDCConflict()

        self.log.debug("%s: set_cfg_module: module=%s", self, module)

        if self._cfg_module != module:
            self._cfg_module = module
            self.cfg_module_changed.emit(module)
            self.cfg_profile_changed.emit(module.profile)
            self._update_config_addresses()

    def __str__(self):
        return "am.Device(id=%s, b=%d, a=%d, mrc=%s, hw=%s, cfg=%s)" % (
                hex(id(self)), self.bus, self.address, self.mrc, self.hw, self.cfg)

    def _update_idc_conflict(self):
        conflict = self.has_hw and self.has_cfg and self.hw.idc != self.cfg.idc

        if conflict != self._idc_conflict:
            self._idc_conflict = conflict
            self.log.debug("%s: idc conflict=%s", self, conflict)
            self.idc_conflict_changed.emit(self.idc_conflict)

    def has_idc_conflict(self):
        """True if hardware and config IDCs differ."""
        return self._idc_conflict

    # ===== config ==== #
    def update_config_applied(self):
        old_state = self.is_config_applied()
        new_state = None # unknown

        if self.idc_conflict:
            new_state = False
        elif self.has_hw and self.has_cfg:
            hw_mem  = self.hw.get_cached_memory_ref()
            cfg_mem = self.cfg.get_cached_memory_ref()

            try:
                #self.log.debug("update_config_applied: addresses=%s", self._config_addresses)
                new_state = all((hw_mem[k] == cfg_mem[k] for k in self._config_addresses))
                self.log.debug("update_config_applied: old_state=%s, new_state=%s (memory compare)",
                        old_state, new_state)
            except KeyError as e:
                hw_keys  = set(hw_mem.keys())
                cfg_keys = set(cfg_mem.keys())
                self.log.debug("update_config_applied: missing address: %s", e)
                self.log.debug("update_config_applied: hw_keys =%s", hw_keys)
                self.log.debug("update_config_applied: cfg_keys=%s", cfg_keys)
                self.log.debug("update_config_applied: hw.diff(cfg)=%s", hw_keys.difference(cfg_keys))
                self.log.debug("update_config_applied: cfg.diff(hw)=%s", cfg_keys.difference(hw_keys))
                new_state = None # Unknown

            if new_state is True:
                extensions_match = self.hw.get_extensions() == self.cfg.get_extensions()
                new_state = new_state and extensions_match
                self.log.debug("update_config_applied: old_state=%s, new_state=%s (extension compare)",
                        old_state, new_state)

        if new_state != old_state:
            self.log.debug("update_config_applied: %s: config_applied changed: %s", self, new_state)
            self._config_applied = new_state
            self.config_applied_changed.emit(new_state)

    def _update_config_addresses(self):
        if self.idc_conflict:
            self._config_addresses = set()
            self.update_config_applied()
            return

        def on_done(f):
            self._config_addresses = set((p.address for p in f.result()))
            self.log.debug("_update_config_addresses: %s", self._config_addresses)
            self.update_config_applied()

        self.get_config_parameters().add_done_callback(on_done)

    def is_config_applied(self):
        """True if hardware and config values are equal."""
        return self._config_applied

    def create_config(self, name=str(), create_mrc_config=True):
        """Creates a config for this device using the default values from the
        device profile.

        Preconditions:
          - self.cfg must be None: device must not have a config yet
          - self.profile must be set: a device profile is needed to create the
            config with the proper idc and initial values
          - create_mrc_config must be True or self.mrc.cfg must be set
        """
        if self.cfg is not None:
            raise RuntimeError("device config exists")

        if self.profile is None:
            raise RuntimeError("device profile not set")

        if not create_mrc_config and self.mrc.cfg is None:
            raise RuntimeError("mrc config missing")

        cfg = cm.make_device_config(bus=self.bus, address=self.address,
                idc=self.profile.idc, name=name, device_profile=self.profile)

        if self.mrc.cfg is None:
            self.mrc.create_config()

        self.mrc.cfg.add_device(cfg)

        return cfg

    def get_config_parameters(self):
        if self.cfg_module is not None and hasattr(self.cfg_module, 'get_config_parameters'):
            return self.cfg_module.get_config_parameters(self)

        return future.Future().set_result(
                self.cfg_profile.get_config_parameters())

    def get_critical_config_parameters(self):
        ret = future.Future()

        def on_done(f):
            try:
                ret.set_result([p for p in f.result() if p.critical])
            except Exception as e:
                ret.set_exception(e)

        self.get_config_parameters().add_done_callback(on_done)

        return ret

    def get_non_critical_config_parameters(self):
        ret = future.Future()

        def on_done(f):
            try:
                ret.set_result([p for p in f.result() if not p.critical])
            except Exception as e:
                ret.set_exception(e)

        self.get_config_parameters().add_done_callback(on_done)

        return ret

    # ===== specialized device & device widget ===== #
    def make_specialized_device(self, read_mode, write_mode):
        try:
            module = self.module
        except IDCConflict:
            module = self.cfg_module if read_mode & util.CONFIG else self.hw_module

        return module.device_class(self, read_mode, write_mode)

    def make_device_widget(self, display_mode, write_mode, make_settings=None, parent=None):
        try:
            module = self.module
        except IDCConflict:
            module = self.cfg_module if display_mode & util.CONFIG else self.hw_module

        ret = module.device_ui_class(
                device=self.make_specialized_device(display_mode, write_mode),
                display_mode=display_mode,
                write_mode=write_mode,
                parent=parent)

        ret.make_settings = make_settings

        return ret

    def has_specialized_class(self):
        return self.module.has_specialized_class()

    def has_widget_class(self):
        return self.module.has_widget_class()

    def get_device_name(self):
        return self.profile.name

    def has_address_conflict(self):
        return self.has_hw and self.hw.address_conflict

    # ===== polling ===== #
    def add_default_polling_subscription(self, subscriber):
        if not self.has_hw:
            raise RuntimeError("Hardware not present")

        self.log.debug("Adding poll subscription (idc=%d, %s) for %s",
                self.hw.idc, self.hw_profile.name, subscriber)

        self.hw.add_poll_items(subscriber, self.hw_profile.get_volatile_addresses())

    def remove_polling_subscriber(self, subscriber):
        if not self.has_hw:
            raise RuntimeError("Hardware not present")

        self.hw.remove_polling_subscriber(subscriber)
        self.log.debug("Removed poll subscriber %s", subscriber)

    mrc             = pyqtProperty(object, get_mrc, set_mrc, notify=mrc_changed)

    idc_conflict    = pyqtProperty(bool, has_idc_conflict, notify=idc_conflict_changed)
    idc             = pyqtProperty(int, get_idc, notify=idc_changed)
    hw_idc          = pyqtProperty(int, get_hw_idc, notify=hw_idc_changed)
    cfg_idc         = pyqtProperty(int, get_cfg_idc, notify=cfg_idc_changed)

    module          = pyqtProperty(object, get_module, set_module, notify=module_changed)
    hw_module       = pyqtProperty(object, get_hw_module, set_hw_module, notify=hw_module_changed)
    cfg_module      = pyqtProperty(object, get_cfg_module, set_cfg_module, notify=cfg_module_changed)

    profile         = pyqtProperty(object, get_profile, notify=profile_changed)
    hw_profile      = pyqtProperty(object, get_hw_profile, notify=hw_profile_changed)
    cfg_profile     = pyqtProperty(object, get_cfg_profile, notify=cfg_profile_changed)

    config_applied  = pyqtProperty(bool, is_config_applied, notify=config_applied_changed)
    address_conflict = pyqtProperty(bool, has_address_conflict)

class Director(object):
    """Manages the app_model tree.
    Subscribes to changes to both the hardware and config trees and updates the
    app_model tree.
    """
    def __init__(self, app_registry, device_registry):
        self.log                = util.make_logging_source_adapter(__name__, self)
        self.registry           = app_registry
        self.device_registry    = device_registry

        self._hw_registry_set(app_registry, None, app_registry.hw)
        self._cfg_registry_set(app_registry, None, app_registry.cfg)

        app_registry.hardware_set.connect(self._hw_registry_set)
        app_registry.config_set.connect(self._cfg_registry_set)

    def _make_device(self, bus, address, hw_device=None, cfg_device=None):
        # hardware idc has precedence for module selection
        idc     = hw_device.idc if hw_device is not None else cfg_device.idc
        module  = self.device_registry.get_device_module(idc)

        self.log.debug("_make_device: bus=%d, addr=%d, hw_device=%s, cfg_device=%s, idc=%d, module=%s",
                bus, address, hw_device, cfg_device, idc, module)

        return Device(bus=bus, address=address,
                hw_device=hw_device, cfg_device=cfg_device,
                hw_module=module, cfg_module=module)

    def _maybe_update_device_module(self, app_device):
        if app_device.idc_conflict:
            app_device.set_hw_module(self.device_registry.get_device_module(app_device.hw.idc))
            app_device.set_cfg_module(self.device_registry.get_device_module(app_device.cfg.idc))
        else:
            app_device.set_module(self.device_registry.get_device_module(app_device.idc))

    # ===== hardware side =====
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
            app_mrc = MRC(url=mrc.url, mrc_registry=self.registry, hw_mrc=mrc)
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
        model_util.set_default_device_extensions(device, self.device_registry)
        app_mrc = self.registry.find_mrc_by_hardware(device.mrc)
        app_device = app_mrc.get_device(device.bus, device.address)
        if app_device is None:
            app_device = self._make_device(bus=device.bus, address=device.address, hw_device=device)
            app_mrc.add_device(app_device)
        else:
            app_device.hw = device
            self._maybe_update_device_module(app_device)
        device.idc_changed.connect(partial(self._maybe_update_device_module, app_device=app_device))

    def _hw_device_about_to_be_removed(self, device):
        self.log.debug("_hw_device_about_to_be_removed: device=%s", device)
        app_mrc = self.registry.find_mrc_by_hardware(device.mrc)
        app_device = app_mrc.get_device(device.bus, device.address)
        app_device.hw = None
        if app_device.cfg is None:
            app_mrc.remove_device(app_device)
        else:
            self._maybe_update_device_module(app_device)

    # ===== config side =====
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

            gen = (mrc for mrc in new_cfg_reg.mrcs
                    if new_cfg_reg.autoconnect and mrc.autoconnect)

            for cfg_mrc in gen:
                self.log.info("auto connecting %s", cfg_mrc)
                hw_mrc = self.registry.hw.get_mrc(cfg_mrc.url)
                if not hw_mrc:
                    add_mrc_connection(self.registry.hw, cfg_mrc.url, True)
                elif hw_mrc.is_disconnected():
                    hw_mrc.connect()

    def _cfg_mrc_added(self, mrc):
        self.log.debug("_cfg_mrc_added: %s", mrc)

        # Search by URL here instead of using find_mrc_by_config() as there is
        # no app_model.MRC pointing to newly added MRC config yet.
        app_mrc = self.registry.get_mrc(mrc.url)

        if app_mrc is None:
            app_mrc = MRC(url=mrc.url, mrc_registry=self.registry, cfg_mrc=mrc)
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
        was_modified = device.modified
        model_util.set_default_device_extensions(device, self.device_registry)
        if not was_modified:
            device.modified = False
        app_mrc = self.registry.find_mrc_by_config(device.mrc)
        app_device = app_mrc.get_device(device.bus, device.address)
        if app_device is None:
            app_device = self._make_device(bus=device.bus, address=device.address, cfg_device=device)
            app_mrc.add_device(app_device)
        else:
            app_device.cfg = device
            self._maybe_update_device_module(app_device)
        device.idc_changed.connect(partial(self._maybe_update_device_module, app_device=app_device))

    def _cfg_device_about_to_be_removed(self, device):
        self.log.debug("_cfg_device_about_to_be_removed: device=%s", device)
        app_mrc = self.registry.find_mrc_by_config(device.mrc)
        app_device = app_mrc.get_device(device.bus, device.address)
        app_device.cfg = None
        if app_device.hw is None:
            app_mrc.remove_device(app_device)
        else:
            self._maybe_update_device_module(app_device)
