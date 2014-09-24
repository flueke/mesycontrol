#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal
import importlib
import os

import app_model
import config
import device_profile
import hw_model
import mrc_connection
import mrc_controller
import util

instance = None

def init(main_file):
    global instance
    if instance is not None:
        raise RuntimeError("ApplicationRegistry already initialized")
    instance = ApplicationRegistry(main_file)
    return instance

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

class ApplicationRegistry(QtCore.QObject):
    mrc_model_added   = pyqtSignal(object) #: hw_model.MRCModel
    mrc_model_removed = pyqtSignal(object) #: hw_model.MRCModel

    mrc_added         = pyqtSignal(object) #: app_model.MRC
    mrc_removed       = pyqtSignal(object) #: app_model.MRC

    device_added      = pyqtSignal(object) #: app_model.Device
    device_removed    = pyqtSignal(object) #: app_model.Device

    def __init__(self, main_file, parent=None):
        super(ApplicationRegistry, self).__init__(parent)
        self.log                = util.make_logging_source_adapter(__name__, self)
        self.main_file          = main_file
        self.bin_dir            = os.path.abspath(os.path.dirname(main_file))
        self.data_dir           = find_data_dir(main_file)
        self.mrc_models         = list()
        self.mrcs               = list()
        self.device_profiles    = set()
        self._object_registry   = dict()

        self.load_system_profiles()

    def shutdown(self):
        for mrc in self.mrcs:
            self.unregister_mrc(mrc)

        for mrc_model in self.mrc_models:
            mrc_model.controller.disconnect()
            self.unregister_mrc_model(mrc_model)

    def load_system_profiles(self):
        # FIXME: use globbing to get the list of files to import (and make
        # cxfreeze distutils install those files to a location outside the zip)
        for mod_name in ('device_profile_mhv4', 'device_profile_mhv4_800v', 'device_profile_mscf16'):
            try:
                #mod = importlib.import_module(mod_name, 'mesycontrol')
                mod = importlib.import_module("mesycontrol." + mod_name)
                device_profile = mod.get_device_profile()
                self.log.debug("Loaded device profile %s", device_profile)
                self.device_profiles.add(device_profile)
            except ImportError as e:
                self.log.error("Error loading device profile from %s: %s", mod_name, str(e))


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

    def get_device_name_by_idc(self, idc):
        return self.get_device_profile_by_idc(idc).name

    def find_data_file(self, filename):
        return os.path.join(self.data_dir, filename)

    def register_mrc_model(self, mrc_model):
        if mrc_model in self.mrc_models:
            return
        mrc_model.setParent(self)
        self.mrc_models.append(mrc_model)
        self.mrc_model_added.emit(mrc_model)

    def unregister_mrc_model(self, mrc_model):
        if mrc_model in self.mrc_models:
            self.mrc_models.remove(mrc_model)
            mrc_model.setParent(None)
            mrc_model.controller.disconnect()
            self.mrc_model_removed.emit(mrc_model)

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

    def get(self, key):
        return self._object_registry.get(key, None)

    def register(self, key, obj):
        self._object_registry[key] = obj

    def unregister(self, key):
        del self._object_registry[key]

    def has_key(self, key):
        return key in self._object_registry

    def make_mrc_connection(self, **kwargs):
        connection       = mrc_connection.factory(**kwargs)
        model            = hw_model.MRCModel()
        model.controller = mrc_controller.MesycontrolMRCController(connection, model)
        self.register_mrc_model(model)

        mrc_config = config.MRCConfig()
        mrc_config.connection_config = config.make_connection_config(connection)

        mrc = app_model.MRC(mrc_model=model, mrc_config=mrc_config)

        self.register_mrc(mrc)

        # Important step: register the newly created mrc_config. Otherwise it
        # would be garbage collected.
        active_setup = self.get('active_setup')

        if active_setup is None:
            active_setup = config.Setup()
            self.register('active_setup', active_setup)

        active_setup.add_mrc_config(mrc.config)

        if 'connect' in kwargs and kwargs['connect']:
            mrc.connect()

        return mrc

    def make_qsettings(self):
        return QtCore.QSettings("mesytec", "mesycontrol")
