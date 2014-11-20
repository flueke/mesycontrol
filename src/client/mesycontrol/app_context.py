#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import pyqtSignal
from qt import pyqtProperty
import os
import importlib

import app_model
import config
import device_profile
import hw_model
import mrc_connection
import mrc_controller
import util
import sys

class Context(QtCore.QObject):
    mrc_added               = pyqtSignal(object) #: app_model.MRC
    mrc_removed             = pyqtSignal(object) #: app_model.MRC
    device_added            = pyqtSignal(object) #: app_model.Device
    device_removed          = pyqtSignal(object) #: app_model.Device
    active_setup_changed    = pyqtSignal(object, object) #: old setup, new setup

    default_device_class    = app_model.Device

    def __init__(self, main_file, parent=None):
        super(Context, self).__init__(parent)
        self.log                    = util.make_logging_source_adapter(__name__, self)
        self.main_file              = sys.executable if getattr(sys, 'frozen', False) else main_file
        self.bin_dir                = os.path.abspath(os.path.dirname(self.main_file))
        self.data_dir               = find_data_dir(self.main_file)
        self.mrc_models             = list()
        self.mrcs                   = list()
        self.device_profiles        = set()
        self.device_classes         = dict()
        self.device_widget_classes  = dict()
        self._active_setup          = None

        self._load_system_profiles()
        self._load_device_classes()

    def shutdown(self):
        for mrc in self.mrcs:
            self.unregister_mrc(mrc)

        for mrc_model in self.mrc_models:
            mrc_model.controller.disconnect()
            self.unregister_mrc_model(mrc_model)

    def _load_system_profiles(self):
        for mod_name in ('device_profile_mhv4', 'device_profile_mscf16'):
            try:
                mod = importlib.import_module("mesycontrol." + mod_name)
                self.log.debug("Loading device profile from %s", mod.__file__)

                device_profile = mod.get_device_profile()
                self.device_profiles.add(device_profile)

                self.log.info("Loaded device profile %s", device_profile)
            except ImportError as e:
                self.log.error("Error loading device profile from %s: %s", mod_name, str(e))

    def _load_device_classes(self):
        for mod_name in ('mhv4', 'mscf16'):
            try:
                mod = importlib.import_module('mesycontrol.' + mod_name)
                self.log.debug("Loading device class from %s", mod.__file__)

                idcs, class_ = mod.get_device_info()

                for idc in idcs:
                    self.device_classes[idc] = class_

                idcs, class_ = mod.get_widget_info()

                for idc in idcs:
                    self.device_widget_classes[idc] = class_

                self.log.info("Loaded device class '%s' for idcs=%s from '%s'",
                        class_.__name__, idcs, mod.__file__)
            except ImportError as e:
                self.log.error("Error loading device class from %s: %s", mod_name, str(e))

    def get_device_class(self, idc):
        return self.device_classes.get(idc, Context.default_device_class)

    def get_device_widget_class(self, idc):
        return self.device_widget_classes.get(idc, None)

    def get_device_profile_by_idc(self, idc):
        try:
            return filter(lambda d: d.idc == idc, self.device_profiles)[0]
        except IndexError:
            return device_profile.make_generic_profile(idc)

    def get_device_profile_by_name(self, name):
        try:
            return filter(lambda d: d.name == name, self.device_profiles)[0]
        except IndexError:
            raise RuntimeError("No device description for name %s" % name)

    def find_data_file(self, filename):
        return os.path.join(self.data_dir, filename)

    def register_mrc_model(self, mrc_model):
        if mrc_model in self.mrc_models:
            return
        mrc_model.setParent(self)
        self.mrc_models.append(mrc_model)

    def unregister_mrc_model(self, mrc_model):
        if mrc_model in self.mrc_models:
            self.mrc_models.remove(mrc_model)
            mrc_model.setParent(None)
            mrc_model.controller.disconnect()

    def register_mrc(self, mrc):
        if mrc in self.mrcs:
            return
        mrc.setParent(self)
        self.register_mrc_model(mrc.model)
        self.mrcs.append(mrc)

        mrc.device_added.connect(self.device_added)
        mrc.device_removed.connect(self.device_removed)

        self.mrc_added.emit(mrc)

    def unregister_mrc(self, mrc):
        if mrc in self.mrcs:
            self.mrcs.remove(mrc)
            mrc.setParent(None)
            self.unregister_mrc_model(mrc.model)
            self.mrc_removed.emit(mrc)

    def find_mrc_by_config(self, mrc_config):
        for mrc in self.mrcs:
            controller = mrc.model.controller
            if hasattr(controller, 'connection'):
                con = controller.connection
                if con.matches_config(mrc_config.connection_config):
                    return mrc
        return None

    def get_mrcs(self):
        return list(self.mrcs)

    def find_connection_by_config(self, connection_config):
        for mrc_model in self.mrc_models:
            controller = mrc_model.controller
            if hasattr(controller, 'connection'):
                connection = controller.connection
                if connection.matches_config(connection_config):
                    return connection
        return None

    def make_mrc_connection(self, **kwargs):
        try:
            mrc_config = kwargs['mrc_config']
            connection = mrc_connection.factory(config=mrc_config.connection_config)
        except KeyError:
            connection = mrc_connection.factory(**kwargs)
            mrc_config = config.MRCConfig()
            mrc_config.connection_config = config.make_connection_config(connection)

        model            = hw_model.MRCModel()
        model.controller = mrc_controller.MRCController(connection, model)
        self.register_mrc_model(model)

        mrc = app_model.MRC(mrc_model=model, mrc_config=mrc_config, context=self)

        self.register_mrc(mrc)

        # Important step: register the newly created mrc_config. Otherwise it
        # would be garbage collected.
        active_setup = self.get_active_setup()

        if active_setup is None:
            active_setup = config.Setup()
            self.set_active_setup(active_setup)

        if not active_setup.contains_mrc_config(mrc.config):
            active_setup.add_mrc_config(mrc.config)

        if 'connect' in kwargs and kwargs['connect']:
            mrc.connect()

        return mrc

    def make_qsettings(self):
        return QtCore.QSettings("mesytec", "mesycontrol")

    def get_active_setup(self):
        return self._active_setup

    def set_active_setup(self, setup):
        if self._active_setup != setup:
            old_setup = self._active_setup
            self._active_setup = setup
            self.active_setup_changed.emit(old_setup, setup)

    active_setup = pyqtProperty(object, get_active_setup, set_active_setup, notify=active_setup_changed)

def find_data_dir(main_file):
    """Locates the directory used for data files.
    Recursively follows symlinks until the location of main_file is known.
    Returns the name of the directory of the location of the main file.
    """
    while os.path.islink(main_file):
        lnk = os.readlink(main_file)
        if os.path.isabs(lnk):
            main_file = lnk
        else:
            main_file = os.path.abspath(os.path.join(os.path.dirname(main_file), lnk))
    return os.path.dirname(os.path.abspath(main_file))
