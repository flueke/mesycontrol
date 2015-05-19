#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import Qt
from functools import partial

import basic_tree_model as btm

QModelIndex = QtCore.QModelIndex

class ConfigTreeModel(btm.BasicTreeModel):
    def columnCount(self, parent=QModelIndex()):
        return 3

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return str(section)
        return None

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None
        return idx.internalPointer().data(idx.column(), role)

# Node types and displayed data
# SetupNode     filename, modified
# MRCNode       name, url
# BusNode       bus number
# DeviceNode    address, name, type, 

class SetupNode(btm.BasicTreeNode):
    def __init__(self, setup, parent=None):
        """setup should be an instance of app_model.MRCRegistry."""
        super(SetupNode, self).__init__(ref=setup, parent=parent)
        setup.config_model_set.connect(self._model_set)

    def _model_set(self, setup):
        f = partial(self.model.notify_data_changed, self, 0, self.model.columnCount())
        if setup.cfg is not None:
            setup.cfg.filename_changed.connect(f)
            setup.cfg.modified_changed.connect(f)
        f()
           
    def data(self, column, role):
        setup = self.ref.cfg
        if column == 0 and role == Qt.DisplayRole:
            ret = setup.filename if setup is not None and len(setup.filename) else "<unsaved setup>"
            if setup is not None and setup.modified:
                ret += "*"
            return ret

class MRCNode(btm.BasicTreeNode):
    def __init__(self, mrc, parent=None):
        """mrc should be an instance of app_model.MRC"""
        super(MRCNode, self).__init__(ref=mrc, parent=parent)
        mrc.config_model_set.connect(self._model_set)

    def _model_set(self, mrc):
        f = partial(self.model.notify_data_changed, self, 0, self.model.columnCount())
        f()

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            #if self.ref is not None:
            return self.ref.url

class BusNode(btm.BasicTreeNode):
    def __init__(self, bus_number, parent=None):
        super(BusNode, self).__init__(parent=parent)
        self.bus_number = bus_number

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            return str(self.bus_number)

class DeviceNode(btm.BasicTreeNode):
    def __init__(self, device, parent=None):
        super(DeviceNode, self).__init__(ref=device, parent=parent)
        device.config_model_set.connect(self._model_set)

    def _model_set(self, device):
        f = partial(self.model.notify_data_changed, self, 0, self.model.columnCount())
        f()

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            return "%s %s" % (self.ref.address,
                    self.ref.idc if self.ref is not None else "<not in config>")
