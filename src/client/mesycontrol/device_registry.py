#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import copy
import importlib

import device_profile
import devices
import util

class DeviceRegistry(object):
    def __init__(self):
        self.log = util.make_logging_source_adapter(__name__, self)
        self.profile_modules        = dict()
        self.profiles               = dict()    # DeviceProfile instances
        self.device_modules         = dict()
        self.device_classes         = dict()
        self.device_ui_classes      = dict()

    def load_system_deviceprofile_modules(self):
        for mod_name in devices.profile_modules:
            try:
                self.load_device_profile_module("mesycontrol.devices." + mod_name)
            except Exception:
                self.log.exception("Error loading device profile module '%s'", mod_name)

    def load_system_device_modules(self):
        for mod_name in devices.device_modules:
            try:
                self.load_device_module("mesycontrol.devices." + mod_name)
            except Exception:
                self.log.exception("Error loading device module '%s'", mod_name)

    def load_device_profile_module(self, module_name):
        module = importlib.import_module(module_name)
        idc    = module.idc
        self.profile_modules[idc] = module
        self.profiles[idc] = device_profile.from_dict(module.profile_dict)
        self.log.debug("Loaded device profile from '%s' for idc=%d", module_name, idc)

    def load_device_module(self, module_name):
        module = importlib.import_module(module_name)
        idc    = module.idc
        self.device_modules[idc]    = module
        self.device_classes[idc]    = module.device_class
        self.device_ui_classes[idc] = module.device_ui_class
        self.log.debug("Loaded device module from '%s' for idc=%d", module_name, idc)

    def get_profile_module(self, idc):
        return self.profile_modules[idc]

    def get_profile(self, idc):
        try:
            return copy.deepcopy(self.profiles[idc])
        except KeyError:
            return device_profile.make_generic_profile(idc)

    def get_device_module(self, idc):
        return self.device_modules[idc]

    def get_device_class(self, idc):
        return self.device_classes[idc]

    def get_device_ui_class(self, idc):
        return self.device_ui_classes[idc]

    def get_device_names(self):
        """Returns a list of (idc, name) tuples."""
        return sorted(((p.idc, p.name) for p in self.profiles.values()))

    def get_device_name(self, idc):
        return self.get_profile(idc).name

    def get_parameter_name_mapping(self):
        """Returns a mapping of device_idc to a dictionary of param_address ->
        param_name. Basically the known parameter names for each device."""
        ret = dict()
        for idc, profile in self.profiles.iteritems():
            d = ret.setdefault(idc, dict())
            for pp in profile.parameters:
                d[pp.address] = pp.name
        return ret
