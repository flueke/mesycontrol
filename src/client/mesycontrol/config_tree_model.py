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
        return 1

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        return None

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None
        return idx.internalPointer().data(idx.column(), role)

# Node types and displayed data
# SetupNode     filename, modified (*); <unsaved setup> if not filename
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
            setup.cfg.mrc_added.connect(f)
            setup.cfg.mrc_removed.connect(f)
        f()
           
    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            setup = self.ref.cfg

            if len(setup):
                ret = setup.filename if len(setup.filename) else "<unsaved setup>"

                if setup.modified:
                    ret += "*"
                return ret

            return "<empty setup>"

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
            mrc = self.ref
            app_url = mrc.url
            cfg_url = mrc.cfg.url if mrc.cfg else str()
            return "app_url=%s | cfg_url=%s" % (app_url, cfg_url)

class BusNode(btm.BasicTreeNode):
    def __init__(self, bus_number, parent=None):
        super(BusNode, self).__init__(parent=parent)
        self.bus_number = bus_number

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            mrc = self.parent.ref
            if mrc.cfg:
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
            #return "%s %s" % (self.ref.address,
            #        self.ref.idc if self.ref is not None else "<not in config>")
            device = self.ref
            if device.cfg:
                address = device.cfg.address
                idc = device.cfg.idc
                return "%X | idc=%d | cfg=%s" % (address, idc, bool(device.cfg))
