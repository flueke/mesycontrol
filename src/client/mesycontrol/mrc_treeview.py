#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import pyqtSlot
from PyQt4.QtCore import QModelIndex
from PyQt4.QtCore import Qt
from functools import partial
import util
import weakref
from mesycontrol import application_model
from util import TreeNode

# app_model -> list(MRCConnection) -> MRCModel (name, status) -> DeviceModels (name, idc, rc, status, bus, dev)
# Columns: Item, Status, RC, RW

# app_model       -> list of Setup
# Setup           -> list of MRCConnection/ConnectionConfig, filename, is_modified?
# MRCConnection   -> MRCModel/MRCConfig
# MRCModel        -> list of DeviceModel/DeviceConfig
# MRCConfig       -> name
# DeviceModel     -> idc, rc, bus, dev, in_setup?
# DeviceConfig    -> name, description, is_modified?




# ApplicationModel.setups -> list of Setup
# SetupNode
#  - Setup
# MRCNode
#  - MRCModel
#  - MRCConfig
# DeviceNode
#  - DeviceModel
#  - DeviceConfig
# Additionally:
# BusNode
#  - MRCModel
#  - bus

class MRCNode(TreeNode):
    def __init__(self, mrc, parent):
        super(MRCNode, self).__init__(mrc, parent)
        self.children = [BusNode(mrc, bus, self) for bus in range(2)] # XXX: 'lost' bus will not show up

    def flags(self, column):
        if column == 0:
            ret = (Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)
            if self.checkable:
                ret |= Qt.ItemIsUserCheckable
            return ret
        return None

    def data(self, column, role):
        if column == 0:
            if role in (Qt.DisplayRole, Qt.StatusTipRole, Qt.ToolTipRole):
                if len(self.ref.name):
                    return '%s (%s)' % (self.ref.name, self.ref.connection.get_info())
                return 'MRC-1 at %s' % (self.ref.connection.get_info())
            elif role == Qt.EditRole:
                return self.ref.name
            elif role == Qt.DecorationRole:
                return QtGui.QColor(Qt.green)
            elif role == Qt.BackgroundRole:
                return QtGui.QBrush(Qt.red)
            elif role == Qt.CheckStateRole and self.checkable:
                return Qt.Checked

    def set_data(self, column, value, role):
        if column == 0:
            if role == Qt.EditRole:
                self.ref.name = value.toString()
                return True
            elif role == Qt.CheckStateRole:
                print "check0ring!"
                return True
        return False

    def context_menu(self):
        ret = QtGui.QMenu()
        ret.addAction("Scanbus").triggered.connect(self._slt_scanbus)
        if self.ref.is_connected():
            ret.addAction("Disconnect").triggered.connect(self._slt_disconnect)
        else:
            ret.addAction("Connect").triggered.connect(self._slt_connect)
        return ret

    def _slt_scanbus(self):
        for i in range(2):
            self.ref.scanbus(i)

    def _slt_connect(self):
        self.ref.connection.connect()

    def _slt_disconnect(self):
        self.ref.connection.disconnect()

class BusNode(TreeNode):
    def __init__(self, mrc, bus, parent):
        super(BusNode, self).__init__(mrc, parent)
        self.bus = bus

        for dev in mrc.device_models[bus].iterkeys():
            device = mrc.device_models[bus][dev]
            self.children.append(DeviceNode(device, self))

    def data(self, column, role):
        if column == 0:
            if role in (Qt.StatusTipRole, Qt.ToolTipRole):
                return "Bus %d" % self.bus
            elif role == Qt.DisplayRole:
                return str(self.bus)
        return None

    def context_menu(self):
        ret = QtGui.QMenu()
        ret.addAction("Scanbus").triggered.connect(self._slt_scanbus)
        return ret

    def _slt_scanbus(self):
        self.ref.scanbus(self.bus)

class DeviceNode(TreeNode):
    def __init__(self, device, parent):
        super(DeviceNode, self).__init__(device, parent)

    def flags(self, column):
        if column in (0,):
            ret =  (Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)
            if self.checkable:
                ret |= Qt.ItemIsUserCheckable
            return ret
        return None

    def data(self, column, role):
        device = self.ref
        if column == 0:
            if role in (Qt.DisplayRole, Qt.StatusTipRole, Qt.ToolTipRole):
                name = '<unnamed>' if device.name is None else device.name
                if not len(name):
                    name = '<unnamed>'
                return '%2d %s (%s, IDC=%d)' % (
                        device.dev, name, device.description.name, device.idc)
            elif role == Qt.EditRole:
                return device.name
            elif role == Qt.CheckStateRole and self.checkable:
                return Qt.PartiallyChecked
        elif column == 1:
            if role in (Qt.DisplayRole,):
                return "on" if device.rc else "off"
            elif role in (Qt.StatusTipRole, Qt.ToolTipRole):
                return "RC Status (double click to toggle)"
        return None

    def set_data(self, column, value, role):
        if role == Qt.EditRole:
            if column == 0:
                self.ref.name = value.toString()
                return True
        return False

    def context_menu(self):
        ret = QtGui.QMenu()
        ret.addAction("Toggle RC").triggered.connect(self._slt_toggle_rc)
        return ret

    def _slt_toggle_rc(self):
        self.ref.set_rc(not self.ref.rc)

    def double_clicked(self):
        self._slt_toggle_rc()

class MRCTreeModel(QtCore.QAbstractItemModel):
    def __init__(self, parent=None):
        super(MRCTreeModel, self).__init__(parent)
        self.root = TreeNode(None, None)
        self.setup_edit_mode = False

    def set_setup_edit_mode(self, edit_mode_on_off):
        changed = self.setup_edit_mode != edit_mode_on_off
        if changed:
            for node in self.root.children:
                node.checkable = edit_mode_on_off
            self.setup_edit_mode = edit_mode_on_off
            self.dataChanged.emit(QModelIndex(), QModelIndex())


    def add_mrc(self, mrc):
        mrc_node = MRCNode(mrc, self.root)
        mrc.sig_device_added.connect(partial(self._slt_device_added, mrc_node=mrc_node))

        self.beginInsertRows(QModelIndex(), len(self.root.children), len(self.root.children))
        self.root.children.append(mrc_node)
        self.endInsertRows()

    def _slt_device_added(self, device, mrc_node):
        bus_node = filter(lambda n: n.bus == device.bus, mrc_node.children)[0]
        bus_idx  = self.index(bus_node.row, 0, self.index(mrc_node.row, 0, QModelIndex()))

        device_node = DeviceNode(device, bus_node)
        device.sig_rc_changed.connect(partial(self._slt_device_rc_changed, device_node=device_node))

        self.beginInsertRows(bus_idx, len(bus_node.children), len(bus_node.children))
        bus_node.children.append(device_node)
        self.endInsertRows()

    def _slt_device_rc_changed(self, rc, device_node):
        idx = self.createIndex(device_node.row, 1, device_node)
        self.dataChanged.emit(idx, idx)

    def index(self, row, col, parent=QModelIndex()):
        if not parent.isValid():
            return self.createIndex(row, col, self.root.children[row])
        parent_node = parent.internalPointer()
        return self.createIndex(row, col, parent_node.children[row])

    def parent(self, idx):
        if not idx.isValid():
            return QModelIndex()
        node = idx.internalPointer()
        if node.parent() is None:
            return QModelIndex()
        return self.createIndex(node.parent().row, 0, node.parent())

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(self.root.children)
        node = parent.internalPointer()
        return len(node.children)

    def columnCount(self, parent=QModelIndex()):
        return 2

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return "Name"
            elif section == 1:
                return "RC"
        return None

    def flags(self, idx):
        ret = None
        if idx.isValid():
            try:
                ret = idx.internalPointer().flags(idx.column())
            except NotImplementedError:
                pass
        return ret if ret is not None else super(MRCTreeModel, self).flags(idx)

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
        return super(MRCTreeModel, self).setData(idx, value, role)

class MRCTreeWidget(QtGui.QWidget):
    def __init__(self, model=None, parent=None):
        super(MRCTreeWidget, self).__init__(parent)
        edit_mode_button = QtGui.QPushButton("Setup Edit Mode", toggled=self._slt_edit_mode_toggled)
        edit_mode_button.setCheckable(True)
        edit_mode_button.setChecked(False)

        self.tree_view = MRCTreeView(model, self)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(edit_mode_button)
        layout.addWidget(self.tree_view)
        self.setLayout(layout)

    def _slt_edit_mode_toggled(self, on_off):
        self.tree_view.model().set_setup_edit_mode(on_off)

class MRCTreeView(QtGui.QTreeView):
    def __init__(self, model=None, parent=None):
        super(MRCTreeView, self).__init__(parent)
        if model is None:
            model = MRCTreeModel(self)
        self.setModel(model)
        model.rowsInserted.connect(self._slt_rows_inserted)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._slt_context_menu_requested)
        self.doubleClicked.connect(self._slt_item_doubleclicked)
        self.setMouseTracking(True)

    def _slt_rows_inserted(self, parent_idx, start, end):
        while parent_idx.isValid():
            self.expand(parent_idx)
            parent_idx = parent_idx.parent()

        for i in range(self.model().columnCount(parent_idx)):
            self.resizeColumnToContents(i)

    def _slt_context_menu_requested(self, pos):
        idx = self.indexAt(pos)
        if idx.isValid():
            node = idx.internalPointer()
            menu = node.context_menu()
            if menu is not None:
                action = menu.exec_(self.mapToGlobal(pos))
                print action

    def _slt_item_doubleclicked(self, idx):
        if not (self.model().flags(idx) & Qt.ItemIsEditable):
            node = idx.internalPointer()
            if hasattr(node, 'double_clicked'):
                node.double_clicked()
