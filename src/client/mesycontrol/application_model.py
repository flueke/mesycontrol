#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal
import logging
import os

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

class ApplicationModel(QtCore.QObject):
    """Central application information and object registry.
    Create it like this:
    application_model.instance = application_model.ApplicationModel(
            sys.executable if getattr(sys, 'frozen', False) else __file__)
    """

    sig_connection_added = pyqtSignal(object)

    def __init__(self, main_file, parent = None):
        super(ApplicationModel, self).__init__(parent)

        self.main_file = main_file
        self.bin_dir   = os.path.abspath(os.path.dirname(main_file))
        self.data_dir  = find_data_dir(main_file)

        logging.getLogger(__name__).info("bin_dir =%s", self.bin_dir)
        logging.getLogger(__name__).info("data_dir=%s", self.data_dir)

        self.device_descriptions = set()
        self.mrc_connections = list()

        self.load_system_descriptions()

    def registerConnection(self, conn):
        conn.setParent(self)
        self.mrc_connections.append(conn)
        self.sig_connection_added.emit(conn)

    def unregisterConnection(self, conn):
        if conn in self.mrc_connections:
            self.mrc_connections.remove(conn)
            conn.disconnect()
            conn.setParent(None) # Makes the underlying QObject collectable

    def shutdown(self):
        for conn in list(self.mrc_connections):
            self.unregisterConnection(conn)
        assert len(self.mrc_connections) == 0

    def load_system_descriptions(self):
        import importlib
        for mod_name in ('device_description_mhv4', 'device_description_mhv4_800v', 'device_description_mscf16'):
            mod = importlib.import_module('mesycontrol.' + mod_name)
            self.device_descriptions.add(mod.get_device_description())

    def get_device_description_by_idc(self, idc):
        try:
            return filter(lambda d: d.idc == idc, self.device_descriptions)[0]
        except IndexError:
            return None

    def get_device_description_by_name(self, name):
        try:
            return filter(lambda d: d.name == name, self.device_descriptions)[0]
        except IndexError:
            return None

    def find_data_file(self, filename):
        return os.path.join(self.data_dir, filename)

instance = None
