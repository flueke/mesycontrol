#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal
import os

import device_description
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
    mrc_model_added   = pyqtSignal(object) #: MRCModel
    mrc_model_removed = pyqtSignal(object) #: MRCModel

    mrc_added         = pyqtSignal(object) #: MRC
    mrc_removed       = pyqtSignal(object) #: MRC

    def __init__(self, main_file, parent=None):
        super(ApplicationRegistry, self).__init__(parent)
        self.log        = util.make_logging_source_adapter(__name__, self)
        self.main_file  = main_file
        self.bin_dir    = os.path.abspath(os.path.dirname(main_file))
        self.data_dir   = find_data_dir(main_file)
        self.mrc_models = list()
        self.mrcs       = list()
        self.device_descriptions = set()
        self._object_registry = dict()

        self.load_system_descriptions()

    def shutdown(self):
        for mrc in self.mrcs:
            self.unregister_mrc(mrc)

        for mrc_model in self.mrc_models:
            mrc_model.controller.disconnect()
            self.unregister_mrc_model(mrc_model)

    def load_system_descriptions(self):
        # FIXME: use globbing to get the list of files to import (and make
        # cxfreeze distutils install those files to a location outside the zip)
        import importlib
        for mod_name in ('device_description_mhv4', 'device_description_mhv4_800v', 'device_description_mscf16'):
            try:
                #mod = importlib.import_module(mod_name, 'mesycontrol')
                mod = importlib.import_module("mesycontrol." + mod_name)
                device_description = mod.get_device_description()
                self.log.debug("Loaded device description %s", device_description)
                self.device_descriptions.add(device_description)
            except ImportError as e:
                self.log.error("Error loading device description from %s: %s", mod_name, str(e))


    def get_device_description_by_idc(self, idc):
        try:
            return filter(lambda d: d.idc == idc, self.device_descriptions)[0]
        except IndexError:
            return device_description.make_generic_description(idc)

    def get_device_description_by_name(self, name):
        try:
            return filter(lambda d: d.name == name, self.device_descriptions)[0]
        except IndexError:
            raise RuntimeError("No device description for name %s" % name)

    def get_device_name_by_idc(self, idc):
        return self.get_device_description_by_idc(idc).name

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
