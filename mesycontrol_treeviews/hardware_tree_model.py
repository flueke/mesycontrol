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
        return 3

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return str(section)
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
        mrc.hardware_model_set.connect(self._model_set)

    def _model_set(self, mrc):
        f = partial(self.model.notify_data_changed, self, 0, 0)
        f()

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            return "MRCNode %s" % hex(id(self))

class BusNode(btm.BasicTreeNode):
    def __init__(self, bus_number, parent=None):
        super(BusNode, self).__init__(parent=parent)
        self.bus_number = bus_number

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            return str(self.bus_number)

class DeviceNode(btm.BasicTreeNode):
    def __init__(self, device=None, bus=None, address=None, parent=None):
        super(DeviceNode, self).__init__(ref=device, parent=parent)
        self._bus = bus
        self._address = address

    def get_bus(self):
        return self._bus if self.ref is None else self.ref.bus

    def get_address(self):
        return self._address if self.ref is None else self.ref.address

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            return "DeviceNode %s %s" % (hex(id(self)), (self.bus, self.address))

    bus     = property(get_bus)
    address = property(get_address)
