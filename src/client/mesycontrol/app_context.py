#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
import importlib
import os

import app_model as am
import basic_model as bm
import config_model as cm
import device_profile
import devices
import future
import util

class Context(QtCore.QObject):
    def __init__(self, main_file, bin_dir, data_dir, parent=None):
        super(Context, self).__init__(parent)
        self.log                    = util.make_logging_source_adapter(__name__, self)
        self.main_file              = main_file
        self.bin_dir                = bin_dir
        self.data_dir               = data_dir
        self.profile_modules        = dict()
        self.profiles               = dict()    # DeviceProfile instances
        self.device_modules         = dict()
        self.device_classes         = dict()
        self.device_ui_classes      = dict()

        self._load_profile_modules()
        self._load_device_modules()

        self.hw_registry    = bm.MRCRegistry()
        self.setup          = cm.Setup()
        self.director       = am.Director(self.hw_registry, self.setup)
        self.app_registry   = self.director.registry

    def shutdown(self):
        observer = future.FutureObserver()

        def do_disconnect():
            futures = [mrc.disconnect() for mrc in self.hw_registry.get_mrcs()]
            observer.set_future(future.all_done(*futures))

        util.wait_for_signal(signal=observer.done, emitting_callable=do_disconnect, timeout_ms=5000)

    def _load_profile_modules(self):
        for mod_name in devices.profile_modules:
            try:
                module = importlib.import_module("mesycontrol.devices." + mod_name)
                idc    = module.idc
                self.profile_modules[idc] = module
                self.profiles[idc] = device_profile.from_dict(module.profile_dict)
                self.log.debug("Loaded device profile from '%s' for idc=%d", mod_name, idc)
            except Exception:
                self.log.exception("Error loading device profile module '%s'", mod_name)

    def _load_device_modules(self):
        for mod_name in devices.device_modules:
            try:
                module = importlib.import_module("mesycontrol.devices." + mod_name)
                idc    = module.idc
                self.device_modules[idc]    = module
                self.device_classes[idc]    = module.device_class
                self.device_ui_classes[idc] = module.device_ui_class
                self.log.debug("Loaded device module from '%s' for idc=%d", mod_name, idc)
            except Exception:
                self.log.exception("Error loading device module '%s'", mod_name)

    def get_profile_module(self, idc):
        return self.profile_modules[idc]

    # FIXME: should this return a copy of the profile?
    def get_profile(self, idc):
        return self.profiles[idc]

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

    def find_data_file(self, filename):
        return os.path.join(self.data_dir, filename)

    def make_qsettings(self):
        return QtCore.QSettings("mesytec", "mesycontrol")
