#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

# Purpose: Create and test two tree views needed for mesycontrol: the hardware
# tree and the setup tree. Both trees will be shown side by side and must be
# kept in sync (selections, item positions, react to item
# changes/adds/removes/...)

# Components:
# QAbstractItemModels: HardwareTreeModel, SetupTreeModel
# QTreeViews: HardwareTreeView, SetupTreeView
# TreeViewDirector: updates models
# TreeViewWidget: combines HardwareTreeView and SetupTreeView into one Widget

from PyQt4 import QtCore
from PyQt4 import QtGui

# Setup/Config side
class Setup:
    def __init__(self):
        self._mrc_configs = list()

class MRCConfig:
    def __init__(self):
        self._devices = list()

class DeviceConfig:
    # bus, address could be changed by the user. in this case
    # someone has to check the consistency of the tree structures. the combined
    # model might have to be updated.
    def __init__(self, bus, address):
        self._parameters = dict()

class ParameterConfig:
    def __init__(self, address, value=None):
        self._address = address
        self._value   = value

s = Setup()
# ...
future = s.get_mrc("/dev/ttyUSB0").get_device(0, 1).get_parameter(2)
future = s["/dev/ttyUSB0"][0][1][2]

# Hardware side
class Connections:
    def __init__(self):
        self._mrcs = list()

    def add_mrc(self, mrc):
    def remove_mrc(self, mrc):
    def get_mrc(self, url):

class MRC:
    def __init__(self):
        self._devices = list()

    def add_device(self, device):
    def remove_device(self, device):
    def get_device(self, bus, address):

class Device:
    pass

class Parameter:
    def __init__(self, address, value=None):
        self._address = address
        self._value   = value

c = Connections()
# ...
future = c.get_mrc("/dev/ttyUSB0").get_device(0, 1).get_parameter(2)
future = c["/dev/ttyUSB0"][0][1][2]

# Combined Model
class Root:
    def __init__(self):
        self._setup = None
        self._connections = None

class MRC:
    # condition: config.url == hardware.url
    def __init__(self):
        self._config = None
        self._hardware = None

class Device:
    # condition: (config.bus, config.address) == (hardware.bus, hardware.address)
    def __init__(self):
        self._config = None
        self._hardware = None

class MRCCollection:
    def add_mrc(self, mrc)
    def remove_mrc(self, mrc)
    def get_mrc(self, url)

class BasicMRC:
    def __init__(self, url):
        self._url = url
        self._devices = dict()

    def get_url(self):
        return self._url

    def add_device(self, device):
        if (device.bus, device.address) in self._devices:
            raise DuplicateDevice()
        self._devices[(device.bus, device.address)] = device
        device.set_mrc(self)

    def remove_device(self, device):
    def get_device(self, bus, address):

class BasicDevice:
    def __init__(self, bus, address):
        self._bus = bus
        self._address = address

# True for both sides:
# - MRC is identified by its connection URL
# - Bus is identified by its number
# - Device is identified by its (bus, address) pair
# - Parameter is identified by its address
# - The root (Setup, Connections) contains unique MRCs. Duplicates are not allowed
# - Each MRC contains unique devices. No duplicates allowed.

class BasicTreeModel(QtCore.QAbstractItemModel):
    def index(self, row, col, parent=QModelIndex()):
        try:
            root = parent.internalPointer() if parent.isValid() else self.root
            return self.createIndex(row, col, root.children[row])
        except IndexError:
            return QModelIndex()

    def parent(self, idx):
        node = idx.internalPointer() if idx.isValid() else None

        if None in (node, node.parent()):
            return QModelIndex()

        return self.createIndex(node.parent().row, 0, node.parent())

    def rowCount(self, parent=QModelIndex()):
        node = parent.internalPointer() if parent.isValid() else self.root
        return len(node.children)

class HardwareTreeModel(QtCore.QAbstractItemModel):
    def columnCount(self, parent=QModelIndex()):
        return 3

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return str(section)
        return None

    def flags(self, idx):
        ret = None
        if idx.isValid():
            try:
                ret = idx.internalPointer().flags(idx.column())
            except NotImplementedError:
                pass
        return ret if ret is not None else super(HardwareTreeModel, self).flags(idx)

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None
        return idx.internalPointer().data(idx.column(), role)

    def setData(self, idx, value, role = Qt.EditRole):
        ret = False
        if idx.isValid():
            try:
                ret = idx.internalPointer().set_data(idx.column(), value, role)
            except NotImplementedError:
                pass
        if ret:
            self.dataChanged.emit(
                    self.index(idx.row(), 0, idx.parent()),
                    self.index(idx.row(), self.columnCount(idx.parent()), idx.parent()))
            return ret
        return super(HardwareTreeModel, self).setData(idx, value, role)



class HardwareTreeView(QtGui.QTreeView):
    pass

class SetupTreeModel(QtCore.QAbstractItemModel):
    pass

class SetupTreeView(QtGui.QTreeView):
    pass
