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
__email__  = 'f.lueke@mesytec.com'

import importlib

import mesycontrol.device_profile
import mesycontrol.devices
import mesycontrol.util

class VirtualDeviceModule(object):
    def __init__(self, idc):
        self.idc = idc
        self.device_class = None
        self.device_ui_class = None
        self.profile = device_profile.make_generic_profile(idc)

    def has_specialized_class(self):
        return False

    def has_widget_class(self):
        return False

class DeviceRegistry(object):
    """Provides access to device modules."""
    def __init__(self, auto_load_modules=False):
        self.log      = util.make_logging_source_adapter(__name__, self)
        self.modules  = dict()

        if auto_load_modules:
            self.load_system_modules()

    def load_system_modules(self):
        """Load all built-in device modules."""
        for mod_name in devices.__all__:
            try:
                self.load_device_module("mesycontrol.devices." + mod_name)
            except Exception:
                self.log.exception("Error loading device module '%s'", mod_name)

    def load_device_module(self, module_name):
        """Load device class and device UI class from the module specified by
        `module_name'.
        The module has to define three variables: `idc', `device_class' and
        `device_ui_class' containing the device idc, the device class and the
        device UI class to use."""

        module                      = importlib.import_module(module_name)
        self.modules[module.idc]    = module
        module.profile              = device_profile.from_dict(module.profile_dict)

        def has_specialized_class():
            return hasattr(module, 'device_class')

        def has_widget_class():
            return hasattr(module, 'device_ui_class')

        module.has_specialized_class = has_specialized_class
        module.has_widget_class = has_widget_class

        self.log.debug("Loaded device module from '%s' for idc=%d, name=%s",
                module_name, module.idc, module.profile.name)

    def get_device_profile(self, idc):
        try:
            return self.modules[idc].profile
        except KeyError:
            return device_profile.make_generic_profile(idc)

    def get_device_profiles(self):
        return (m.profile for m in self.modules.itervalues())

    def get_device_module(self, idc):
        try:
            return self.modules[idc]
        except KeyError:
            return VirtualDeviceModule(idc)

    def get_device_class(self, idc):
        return self.modules[idc].device_class

    def get_device_ui_class(self, idc):
        return self.modules[idc].device_ui_class

    def get_device_names(self):
        """Returns a list of (idc, name) tuples."""
        return sorted(((p.idc, p.name) for p in self.get_device_profiles()))

    def get_device_name(self, idc):
        return self.get_device_profile(idc).name

    def get_parameter_names(self, idc):
        return self.get_device_profile(idc).get_parameter_names()

    def get_parameter_name_mapping(self):
        """Returns a mapping of device_idc to a dictionary of param_address ->
        param_name. Basically the known parameter names for each device."""

        return dict((idc, self.get_parameter_names(idc))
                for idc in self.modules.keys())
