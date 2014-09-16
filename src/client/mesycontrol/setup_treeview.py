#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import QModelIndex
from PyQt4.QtCore import Qt
import weakref

import config
import config_loader
import config_xml
import mrc_command
import util

column_names  = ('name', 'rc', 'idc', 'queue_size', 'silent_mode', 'write_access')
column_titles = ('Name', 'RC', 'IDC', 'Queue Size', 'Silent Mode', 'Write Access')

def column_index(col_name):
    try:
        return column_names.index(col_name)
    except ValueError:
        return None

def column_name(col_idx):
    try:
        return column_names[col_idx]
    except IndexError:
        return None

class SetupTreeRCComboBoxItemDelegate(QtGui.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(SetupTreeRCComboBoxItemDelegate, self).__init__(parent)

    def createEditor(self, parent, options, idx):
        combo = QtGui.QComboBox(parent)
        combo.addItem("on",  True)
        combo.addItem("off", False)

        # Hack to make the combobox commit immediately after the user selects
        # an item.
        def on_combo_activated(index):
            self.commitData.emit(combo)
            self.closeEditor.emit(combo, QtGui.QAbstractItemDelegate.NoHint)
        combo.activated.connect(on_combo_activated)

        return combo

    def setEditorData(self, editor, idx):
        rc = idx.data(Qt.EditRole).toBool()
        combo_idx = editor.findData(rc)
        if combo_idx >= 0:
            editor.setCurrentIndex(combo_idx)

    def setModelData(self, editor, model, idx):
        combo_idx  = editor.currentIndex()
        combo_data = editor.itemData(combo_idx).toBool()
        model.setData(idx, combo_data)

class TreeNodeWithModel(util.TreeNode):
    def __init__(self, ref, model, parent=None):
        super(TreeNodeWithModel, self).__init__(ref, parent)
        self._model = weakref.ref(model)

    def get_model(self):
        return self._model()

class MRCNode(TreeNodeWithModel):
    sig_remove_mrc = pyqtSignal(object)

    def __init__(self, mrc, model, parent):
        super(MRCNode, self).__init__(mrc, model, parent)
        self.children = [BusNode(mrc, bus, model, self) for bus in range(2)]

        slt = partial(model.node_data_changed, node=self,
                col1=column_index('name'), col2=column_index('name'))
        mrc.connecting.connect(slt)
        mrc.connected.connect(slt)
        mrc.disconnected.connect(slt)
        mrc.ready.connect(slt)
        mrc.name_changed.connect(slt)

        mrc.write_access_changed.connect(partial(model.node_data_changed, node=self,
            col1=column_index('write_access'), col2=column_index('write_access')))

        mrc.silence_changed.connect(partial(model.node_data_changed, node=self,
            col1=column_index('silent_mode'), col2=column_index('silent_mode')))

        mrc.request_queue_size_changed.connect(partial(model.node_data_changed, node=self,
            col1=column_index('queue_size'), col2=column_index('queue_size')))

    def flags(self, column):
        column_name = column_names[column]
        if column_name == 'name':
            ret = (Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)
            if self.checkable:
                ret |= Qt.ItemIsUserCheckable
            return ret
        return None

    def data(self, column, role):
        column_name = column_names[column]
        mrc         = self.ref

        if column_name == 'name':
            if role == Qt.DecorationRole:
                if mrc.is_ready():
                    return QtGui.QColor(Qt.green)
                if mrc.is_connected():
                    return QtGui.QColor(Qt.darkGreen)
                if mrc.is_connecting():
                    return QtGui.QColor(Qt.magenta)
                if mrc.is_disconnected():
                    return QtGui.QColor(Qt.red)

            if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                if mrc.is_ready():
                    return "ready"
                if mrc.is_connected():
                    return "connected"
                if mrc.is_connecting():
                    return "connecting"
                if mrc.is_disconnected():
                    return "disconnected"

            if role == Qt.DisplayRole:
                return str(mrc)
            if role == Qt.EditRole:
                return mrc.name if mrc.is_named() else str()

        if role in (Qt.DisplayRole, Qt.StatusTipRole, Qt.ToolTipRole, Qt.EditRole):
            if column_name == 'queue_size':
                return mrc.get_request_queue_size()
            elif column_name == 'silent_mode':
                return mrc.is_silenced()
            elif column_name == 'write_access':
                return mrc.has_write_access()

        return None

    def set_data(self, column, value, role):
        if role != Qt.EditRole:
            return False

        column_name = column_names[column]
        mrc         = self.ref

        if column_name == 'name':
            name = str(value.toString())
            if not len(name):
                name = None

            mrc.name = value.toString()
            return True

        return False

    def context_menu(self):
        ret = QtGui.QMenu()
        if self.ref.is_connected():
            ret.addAction("Scanbus").triggered.connect(self._slt_scanbus)
            ret.addAction("Disconnect").triggered.connect(self._slt_disconnect)
        else:
            ret.addAction("Connect").triggered.connect(self._slt_connect)
        ret.addAction("Remove from Setup").triggered.connect(self._slt_remove_mrc)
        return ret

    def _slt_scanbus(self):
        for i in range(2):
            self.ref.scanbus(i)

    def _slt_connect(self):
        self.ref.connect()

    def _slt_disconnect(self):
        self.ref.disconnect()

    def _slt_remove_mrc(self):
        self.sig_remove_mrc.emit(self.ref)

class BusNode(TreeNodeWithModel):
    sig_apply_config = pyqtSignal(object)

    def __init__(self, mrc, bus, model, parent):
        super(BusNode, self).__init__(mrc, model, parent)
        self.bus = bus
        self.log = util.make_logging_source_adapter(__name__, self)

        devices = filter(lambda d: d.bus == bus, mrc.get_devices())

        self.log.debug("BusNode(mrc=%s, bus=%d): %d devices present",
                self.ref, self.bus, len(devices))

        self.sig_apply_config.connect(model.sig_apply_config)

        for device in devices:
            device_node = DeviceNode(device, model, self)
            device_node.sig_open_device.connect(model.sig_open_device)
            device_node.sig_save_device_config.connect(model.sig_save_device_config)
            device_node.sig_load_device_config.connect(model.sig_load_device_config)
            device_node.sig_apply_config.connect(self.sig_apply_config)
            self.children.append(device_node)

    def data(self, column, role):
        column_name = column_names[column]
        if column_name == 'name':
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

class DeviceNode(TreeNodeWithModel):
    sig_open_device        = pyqtSignal(object)
    sig_save_device_config = pyqtSignal(object)
    sig_load_device_config = pyqtSignal(object)
    sig_apply_config       = pyqtSignal(object)

    def __init__(self, device, model, parent):
        super(DeviceNode, self).__init__(device, model, parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.log.debug("DeviceNode(id=%d, device=%s, parent=%s)", id(self), self.ref, parent)

        slt = partial(model.node_data_changed, node=self,
                col1=column_index('name'), col2=column_index('name'))
        device.connecting.connect(slt)
        device.connected.connect(slt)
        device.disconnected.connect(slt)
        device.ready.connect(slt)
        device.name_changed.connect(slt)

        device.rc_changed.connect(partial(model.node_data_changed, node=self,
            col1=column_index('rc'), col2=column_index('rc')))

        device.idc_changed.connect(partial(model.node_data_changed, node=self,
            col1=column_index('idc'), col2=column_index('idc')))

        device.request_queue_size_changed.connect(partial(model.node_data_changed, node=self,
            col1=column_index('queue_size'), col2=column_index('queue_size')))

        device.config_set.connect(partial(model.node_data_changed, node=self))
        device.model_set.connect(partial(model.node_data_changed, node=self))

    def flags(self, column):
        column_name = column_names[column]
        if column_name in ('name', 'rc'):
            return (Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)
        return None

    def data(self, column, role):
        column_name = column_names[column]
        device      = self.ref


        if column_name == 'name':
            if role == Qt.DecorationRole:
                if device.is_ready():
                    return QtGui.QColor(Qt.green)
                if device.is_connected():
                    return QtGui.QColor(Qt.darkGreen)
                if device.is_connecting():
                    return QtGui.QColor(Qt.magenta)
                if device.is_disconnected():
                    return QtGui.QColor(Qt.red)

            if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                if device.is_ready():
                    return "ready"
                if device.is_connected():
                    return "connected"
                if device.is_connecting():
                    return "connecting"
                if device.is_disconnected():
                    return "disconnected"

            if role == Qt.DisplayRole:
                return str(device)
            if role == Qt.EditRole:
                return device.name if device.is_named() else str()

        if role in (Qt.DisplayRole, Qt.StatusTipRole, Qt.ToolTipRole, Qt.EditRole):
            if column_name == 'rc':
                if role in (Qt.DisplayRole,):
                    return "on" if device.rc else "off"
                elif role in (Qt.StatusTipRole, Qt.ToolTipRole):
                    return "RC Status (double click to change)"
                elif role == Qt.EditRole:
                    return device.rc
            elif column_name == 'idc':
                return device.idc
            elif column_name == 'queue_size':
                return device.get_request_queue_size()
            elif column_name == 'silent_mode':
                return device.is_silenced()
            elif column_name == 'write_access':
                return device.has_write_access()
        return None

    def set_data(self, column, value, role):
        if role != Qt.EditRole:
            return False

        column_name = column_names[column]
        device      = self.ref

        if column_name == 'name':
            name = str(value.toString())
            if not len(name):
                name = None
            device.name = name
            return True

        if column_name == 'rc':
            device.rc = value
            return True

        return False

    def context_menu(self):
        ret = QtGui.QMenu()
        if self.ref.is_connected():
            ret.addAction("Open").triggered.connect(self._slt_open_device)
            ret.addAction("Toggle RC").triggered.connect(self._slt_toggle_rc)
            ret.addAction("Refresh Memory").triggered.connect(self._slt_refresh_memory)
            if self.ref.config is not None:
                ret.addAction("Apply config").triggered.connect(self._slt_apply_config)
            ret.addAction("Save config to file").triggered.connect(self._slt_save_device_config)
            ret.addAction("Load config from file").triggered.connect(self._slt_load_device_config)
        return ret

    def _slt_open_device(self):
        self.sig_open_device.emit(self.ref)

    def _slt_toggle_rc(self):
        self.ref.set_rc(not self.ref.rc)

    def _slt_refresh_memory(self):
        mrc_command.RefreshMemory(self.ref).start()

    def _slt_save_device_config(self):
        self.sig_save_device_config.emit(self.ref)

    def _slt_load_device_config(self):
        self.sig_load_device_config.emit(self.ref)

    def _slt_apply_config(self):
        self.sig_apply_config.emit(self.ref)

class SetupTreeModel(QtCore.QAbstractItemModel):
    sig_open_device        = pyqtSignal(object)
    sig_remove_mrc         = pyqtSignal(object)
    sig_save_device_config = pyqtSignal(object)
    sig_load_device_config = pyqtSignal(object)
    sig_apply_config       = pyqtSignal(object)

    def __init__(self, parent=None):
        super(SetupTreeModel, self).__init__(parent)
        self.root = util.TreeNode(None)
        self.log  = util.make_logging_source_adapter(__name__, self)

    def node_data_changed(self, node, col1=None, col2=None):
        if col1 is None: col1 = 0
        if col2 is None: col2 = self.columnCount()

        self.log.debug("node_data_changed(node=%s, col1=%s(%d), col2=%s(%d)",
                node, column_name(col1), col1, column_name(col2), col2)

        idx1 = self.createIndex(node.row, col1, node)
        idx2 = self.createIndex(node.row, col2, node)
        self.dataChanged.emit(idx1, idx2)

    def add_mrc(self, mrc):
        mrc_node = MRCNode(mrc, self, self.root)
        mrc.device_added.connect(partial(self._on_device_added, mrc_node=mrc_node))
        mrc_node.sig_remove_mrc.connect(self.sig_remove_mrc)

        self.beginInsertRows(QModelIndex(), len(self.root.children), len(self.root.children))
        self.root.children.append(mrc_node)
        self.endInsertRows()

    def remove_mrc(self, mrc):
        mrc_node   = self.root.find_node_by_ref(mrc)
        parent_idx = self.createIndex(mrc_node.parent().row, 0, mrc_node.parent())

        self.beginRemoveRows(parent_idx, mrc_node.row, mrc_node.row)
        mrc_node.parent().children.remove(mrc_node)
        mrc_node.setParent(None)
        self.endRemoveRows()

    def _on_device_added(self, device, mrc_node):
        bus_node = filter(lambda n: n.bus == device.bus, mrc_node.children)[0]
        bus_idx  = self.index(bus_node.row, 0, self.index(mrc_node.row, 0, QModelIndex()))

        device_node = DeviceNode(device, self, bus_node)
        device_node.sig_open_device.connect(self.sig_open_device)
        device_node.sig_save_device_config.connect(self.sig_save_device_config)
        device_node.sig_load_device_config.connect(self.sig_load_device_config)
        device_node.sig_apply_config.connect(self.sig_apply_config)

        self.beginInsertRows(bus_idx, len(bus_node.children), len(bus_node.children))
        bus_node.children.append(device_node)
        self.endInsertRows()

    def index(self, row, col, parent=QModelIndex()):
        if not parent.isValid():
            return self.createIndex(row, col, self.root.children[row])
        parent_node = parent.internalPointer()
        try:
            return self.createIndex(row, col, parent_node.children[row])
        except IndexError:
            return QModelIndex()

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
        return len(column_names)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            try:
                return column_titles[section]
            except IndexError:
                return None
        return None

    def flags(self, idx):
        ret = None
        if idx.isValid():
            try:
                ret = idx.internalPointer().flags(idx.column())
            except NotImplementedError:
                pass
        return ret if ret is not None else super(SetupTreeModel, self).flags(idx)

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
        return super(SetupTreeModel, self).setData(idx, value, role)

class SetupTreeView(QtGui.QTreeView):
    sig_open_device = pyqtSignal(object)
    sig_remove_mrc  = pyqtSignal(object)

    def __init__(self, model=None, parent=None):
        super(SetupTreeView, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        if model is None:
            model = SetupTreeModel(self)
        self.setModel(model)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._slt_context_menu_requested)
        self.setMouseTracking(True)
        self.setItemDelegateForColumn(column_index('rc'), SetupTreeRCComboBoxItemDelegate())

    def setModel(self, model):
        if self.model() is not None:
            self.model().disconnect(self)
            self.model().setParent(None)

        super(SetupTreeView, self).setModel(model)

        model.rowsInserted.connect(self._slt_rows_inserted)
        model.sig_open_device.connect(self.sig_open_device)
        model.sig_remove_mrc.connect(self.sig_remove_mrc)
        model.sig_save_device_config.connect(self._slt_save_device_config)
        model.sig_load_device_config.connect(self._slt_load_device_config)
        model.sig_apply_config.connect(self._slt_apply_device_config)

    def _slt_rows_inserted(self, parent_idx, start, end):
        while parent_idx.isValid():
            self.expand(parent_idx)
            parent_idx = parent_idx.parent()

        for i in range(self.model().columnCount(parent_idx)):
            self.resizeColumnToContents(i)
        self.setColumnWidth(column_index('rc'), 50)

    def _slt_context_menu_requested(self, pos):
        idx = self.indexAt(pos)
        if idx.isValid():
            node = idx.internalPointer()
            menu = node.context_menu()
            if menu is not None and not menu.isEmpty():
                menu.exec_(self.mapToGlobal(pos))

    def _slt_save_device_config(self, device):
        self.log.debug("save_device_config triggered for %s", device)

        filename = QtGui.QFileDialog.getSaveFileName(self, "Save device config as",
                filter="XML files (*.xml);; *")

        if not len(filename):
            return

        filename = str(filename)

        if not filename.endswith(".xml"):
            filename += ".xml"

        config_builder = config.DeviceConfigBuilder(device)

        pd = QtGui.QProgressDialog(self)
        pd.setMaximum(len(config_builder))
        pd.setValue(0)

        # FIXME: bug somewhere in Command or SequentialCommandGroup: stopped()
        # is emitted before started() if the command group is empty.  instead
        # of config_builder.started.connect(pd.exec_); config_builder.start() I
        # had to use a singleshot timer to start the command as otherwise the
        # pd would never close.
        #
        #def on_started():
        #    print "==== started"

        #def on_stopped():
        #    print "==== stopped"

        #def on_progress_changed(cur, tot):
        #    print "==== progress_changed", cur, tot

        #config_builder.stopped.connect(on_stopped)
        #config_builder.started.connect(on_started)
        #config_builder.progress_changed.connect(on_progress_changed)

        config_builder.progress_changed.connect(pd.setValue)
        config_builder.stopped.connect(pd.accept)
        QtCore.QTimer.singleShot(0, config_builder.start)
        self.log.debug("starting DeviceConfigBuilder for %s", device)
        pd.exec_()

        if pd.wasCanceled():
            self.log.debug("canceling DeviceConfigBuilder for %s as requested", device)
            config_builder.stop()
            return

        if config_builder.has_failed():
            self.log.error("DeviceConfigBuilder for %s failed: %s", device, config_builder.get_exception())
            QtGui.QMessageBox.critical(self, "Error", "Error creating device config: %s" %
                    config_builder.get_exception())
        else:
            try:
                device_config = config_builder.get_result()
                with open(filename, 'w') as f:
                    config_xml.write_device_config_to_file(device_config, f)
            except IOError as e:
                QtGui.QMessageBox.critical(self, "Error", "Writing to %s failed: %s" % (filename, e))
            else:
                QtGui.QMessageBox.information(self, "Info", "Configuration written to %s" % filename)

    def _slt_load_device_config(self, device):
        self.log.debug("load_device_config triggered for %s", device)

        filename = QtGui.QFileDialog.getOpenFileName(self, "Load device config from file",
                filter="XML files (*.xml);; *")

        if not len(filename):
            return

        try:
            cfg = config_xml.parse_file(filename)
            device_config = filter(lambda c: c.idc == device.idc, cfg.get_device_configs())[0]
            loader = config_loader.ConfigLoader(device, device_config)
            pd = QtGui.QProgressDialog(self)
            pd.setMaximum(len(loader))
            pd.setValue(0)
            loader.progress_changed.connect(pd.setValue)
            loader.stopped.connect(pd.accept)
            QtCore.QTimer.singleShot(0, loader.start)
            self.log.debug("Starting ConfigLoader for %s", device)
            pd.exec_()

            if pd.wasCanceled():
                self.log.debug("canceling ConfigLoader for %s as requested", device)
                loader.stop()
                return

            if loader.has_failed():
                self.log.error("ConfigLoader for %s failed: %s", device, loader.get_exception())
                QtGui.QMessageBox.critical(self, "Error", "Error loading device config: %s" %
                        loader.get_exception())
                return

        except IndexError:
            QtGui.QMessageBox.critical(self, "Error", "Error loading device config from %s: No suitable config in file."
                    % (filename, ))
            raise
        except Exception as e:
            QtGui.QMessageBox.critical(self, "Error", "Error loading device config from %s: %s" % (filename, e))
            raise
        else:
            QtGui.QMessageBox.information(self, "Info", "Configuration loaded from %s" % filename)

    def _slt_apply_device_config(self, device):
        self.log.debug("apply_device_config triggered for %s", device)

        if device.config is None:
            return

        try:
            loader = config_loader.ConfigLoader(device, device.config)
            pd = QtGui.QProgressDialog(self)
            pd.setMaximum(len(loader))
            pd.setValue(0)
            loader.progress_changed.connect(pd.setValue)
            loader.stopped.connect(pd.accept)
            QtCore.QTimer.singleShot(0, loader.start)
            self.log.debug("Starting ConfigLoader for %s", device)
            pd.exec_()

            if pd.wasCanceled():
                self.log.debug("canceling ConfigLoader for %s as requested", device)
                loader.stop()
                return

            if loader.has_failed():
                self.log.error("ConfigLoader for %s failed: %s", device, loader.get_exception())
                QtGui.QMessageBox.critical(self, "Error", "Error loading device config: %s" %
                        loader.get_exception())
                return
        except Exception as e:
            QtGui.QMessageBox.critical(self, "Error", "Error applying device config:  %s" % (e,))
            raise


class SetupTreeWidget(QtGui.QWidget):
    def __init__(self, model=None, parent=None):
        super(SetupTreeWidget, self).__init__(parent)
        self.setup_tree_view = SetupTreeView(model, self)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.tree_view)
        self.setLayout(layout)
