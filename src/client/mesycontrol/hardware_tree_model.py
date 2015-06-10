#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import Qt
from functools import partial

import basic_tree_model as btm

QModelIndex = QtCore.QModelIndex

class HardwareTreeModel(btm.BasicTreeModel):
    def columnCount(self, parent=QModelIndex()):
        return 1

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        return None

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None
        return idx.internalPointer().data(idx.column(), role)

class RegistryNode(btm.BasicTreeNode):
    def __init__(self, registry, parent=None):
        """registry should be an instance of app_model.MRCRegistry."""
        super(RegistryNode, self).__init__(ref=registry, parent=parent)

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            return "Connections"

class MRCNode(btm.BasicTreeNode):
    def __init__(self, mrc, parent=None):
        """mrc should be an instance of app_model.MRC"""
        super(MRCNode, self).__init__(ref=mrc, parent=parent)
        mrc.hardware_model_set.connect(self._hw_mrc_set)
        if mrc.hw:
            self._hw_mrc_set(mrc)

    def _hw_mrc_set(self, mrc):
        f = partial(self.model.notify_data_changed, self, 0, self.model.columnCount())
        f()

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            mrc = self.ref
            app_url = mrc.url
            hw_url  = mrc.hw.url if mrc.hw else str()
            return "app_url=%s | hw_url=%s" % (app_url, hw_url)

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
        device.hardware_model_set.connect(self._hw_device_set)

    def _hw_device_set(self, mrc):
        f = partial(self.model.notify_data_changed, self, 0, self.model.columnCount())
        f()

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            device = self.ref
            hw     = device.hw

            address = device.address
            idc     = str(hw.idc) if hw is not None else str()

            return "%X | idc=%s" % (address, idc)
