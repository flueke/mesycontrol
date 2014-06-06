#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal

class ApplicationModel(QtCore.QObject):
    sig_connection_added = pyqtSignal(object)

    def __init__(self, parent = None):
        super(ApplicationModel, self).__init__(parent)
        self.device_descriptions = set()
        self.mrc_connections = list()

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

instance = ApplicationModel()
