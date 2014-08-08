#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4.QtCore import QModelIndex
from PyQt4.QtCore import Qt
from PyQt4.QtCore import pyqtSignal
from functools import partial
import config
import config_xml
import config_loader
import mrc_command
import util
import weakref
from util import TreeNode

column_names  = ('name', 'rc', 'idc', 'connection_state', 'queue_size', 'silent_mode', 'write_access')
column_titles = ('Name', 'RC', 'IDC', 'Connection State', 'Queue Size', 'Silent Mode', 'Write Access')

class TreeNodeWithModel(TreeNode):
    def __init__(self, ref, model, parent=None):
        super(TreeNodeWithModel, self).__init__(ref, parent)
        self._model = weakref.ref(model)

    def get_model(self):
        return self._model()

class SetupNode(TreeNode):
    def __init__(self, setup, parent):
        super(SetupNode, self).__init__(setup, parent)

class MRCNode(TreeNodeWithModel):
    sig_close_mrc = pyqtSignal(object)

    def __init__(self, mrc, model, parent):
        super(MRCNode, self).__init__(mrc, model, parent)
        self.children = [BusNode(mrc, bus, model, self) for bus in range(2)]

        slt = partial(model.node_data_changed, node=self, col1=0, col2=model.columnCount())
        mrc.state_changed.connect(slt)
        mrc.write_access_changed.connect(slt)
        mrc.silence_changed.connect(slt)
        mrc.request_queue_size_changed.connect(slt)

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
        if role in (Qt.DisplayRole, Qt.StatusTipRole, Qt.ToolTipRole, Qt.EditRole):
            if column_name == 'name':
                return str(mrc)
            elif column_name == 'connection_state':
                return mrc.state
            elif column_name == 'queue_size':
                return mrc.get_request_queue_size()
            elif column_name == 'silent_mode':
                return mrc.is_silenced()
            elif column_name == 'write_access':
                return mrc.has_write_access()

                #if len(self.ref.name):
                #    return '%s (%s)' % (self.ref.name, self.ref.connection.get_info())
                #return 'MRC-1 at %s' % (self.ref.connection.get_info())
            #elif role == Qt.EditRole:
            #    return self.ref.name
            #elif role == Qt.DecorationRole:
            #    return QtGui.QColor(Qt.green)
            #elif role == Qt.BackgroundRole:
            #    return QtGui.QBrush(Qt.red)
            #elif role == Qt.CheckStateRole and self.checkable:
            #    return Qt.Checked
        return None

    def set_data(self, column, value, role):
        column_name = column_names[column]
        if role == Qt.EditRole:
            if column_name == 'name':
                self.ref.name = value.toString()
                return True
        #if column == 0:
        #    if role == Qt.EditRole:
        #        self.ref.name = value.toString()
        #        return True
        #    elif role == Qt.CheckStateRole:
        #        print "check0ring!"
        #        return True
        return False

    def context_menu(self):
        ret = QtGui.QMenu()
        ret.addAction("Scanbus").triggered.connect(self._slt_scanbus)
        if self.ref.is_connected():
            ret.addAction("Disconnect").triggered.connect(self._slt_disconnect)
        else:
            ret.addAction("Connect").triggered.connect(self._slt_connect)
        ret.addAction("Close").triggered.connect(self._slt_close)
        return ret

    def _slt_scanbus(self):
        for i in range(2):
            self.ref.model.controller.scanbus(i)

    def _slt_connect(self):
        self.ref.connect()

    def _slt_disconnect(self):
        self.ref.disconnect()

    def _slt_close(self):
        self.sig_close_mrc.emit(self.ref)

class BusNode(TreeNodeWithModel):
    def __init__(self, mrc, bus, model, parent):
        super(BusNode, self).__init__(mrc, model, parent)
        self.bus = bus
        self.log = util.make_logging_source_adapter(__name__, self)

        devices = filter(lambda d: d.model.bus == bus, mrc.get_devices())

        self.log.debug("BusNode(mrc=%s, bus=%d): %d devices present",
                self.ref, self.bus, len(devices))

        for device in devices:
            device_node = DeviceNode(device, model, self)
            device_node.sig_open_device.connect(model.sig_open_device)
            device_node.sig_save_device_config.connect(model.sig_save_device_config)
            device_node.sig_load_device_config.connect(model.sig_load_device_config)
            device_node.sig_apply_config.connect(self.sig_apply_config)
            self.children.append(device_node)

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
        self.ref.model.controller.scanbus(self.bus)

class DeviceNode(TreeNodeWithModel):
    sig_open_device        = pyqtSignal(object)
    sig_save_device_config = pyqtSignal(object)
    sig_load_device_config = pyqtSignal(object)
    sig_apply_config       = pyqtSignal(object)

    def __init__(self, device, model, parent):
        super(DeviceNode, self).__init__(device, model, parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.log.debug("DeviceNode(id=%d, device=%s, parent=%s)", id(self), self.ref, parent)

        slt = partial(model.node_data_changed, node=self, col1=0, col2=model.columnCount())
        device.rc_changed.connect(slt)
        device.idc_changed.connect(slt)
        device.state_changed.connect(slt)
        device.address_conflict_changed.connect(slt)
        device.name_changed.connect(slt)
        device.request_queue_size_changed.connect(slt)

    def flags(self, column):
        if column in (0,):
            ret =  (Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)
            if self.checkable:
                ret |= Qt.ItemIsUserCheckable
            return ret
        return None

    def data(self, column, role):
        column_name = column_names[column]
        device      = self.ref
        if role in (Qt.DisplayRole, Qt.StatusTipRole, Qt.ToolTipRole, Qt.EditRole):
            if column_name == 'name':
                return str(device)
            elif column_name == 'rc':
                if role in (Qt.DisplayRole,):
                    return "on" if device.rc else "off"
                elif role in (Qt.StatusTipRole, Qt.ToolTipRole):
                    return "RC Status (double click to toggle)"
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
        return False

    def context_menu(self):
        ret = QtGui.QMenu()
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

    def double_clicked(self, column):
        column_name = column_names[column]
        if column_name == 'rc':
            self._slt_toggle_rc()

class SetupTreeModel(QtCore.QAbstractItemModel):
    sig_open_device        = pyqtSignal(object)
    sig_close_mrc          = pyqtSignal(object)
    sig_save_device_config = pyqtSignal(object)
    sig_load_device_config = pyqtSignal(object)
    sig_apply_config       = pyqtSignal(object)

    def __init__(self, parent=None):
        super(SetupTreeModel, self).__init__(parent)
        self.root = TreeNode(None)
        self.log  = util.make_logging_source_adapter(__name__, self)

    def node_data_changed(self, node, col1=None, col2=None):
        self.log.debug("node_data_changed(node=%s, col1=%d, col2=%d", node, col1, col2)
        if col1 is None: col1 = 0
        if col2 is None: col2 = self.columnCount()
        idx1 = self.createIndex(node.row, col1, node)
        idx2 = self.createIndex(node.row, col2, node)
        self.dataChanged.emit(idx1, idx2)

    def add_mrc(self, mrc):
        mrc_node = MRCNode(mrc, self, self.root)
        mrc.device_added.connect(partial(self._on_device_added, mrc_node=mrc_node))
        mrc_node.sig_close_mrc.connect(self.sig_close_mrc)

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
        bus_node = filter(lambda n: n.bus == device.model.bus, mrc_node.children)[0]
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
    sig_close_mrc   = pyqtSignal(object)

    def __init__(self, model=None, parent=None):
        super(SetupTreeView, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        if model is None:
            model = SetupTreeModel(self)
        self.setModel(model)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._slt_context_menu_requested)
        self.doubleClicked.connect(self._slt_item_doubleclicked)
        self.setMouseTracking(True)

    def setModel(self, model):
        if self.model() is not None:
            self.model().disconnect(self)

        super(SetupTreeView, self).setModel(model)

        model.rowsInserted.connect(self._slt_rows_inserted)
        model.sig_open_device.connect(self.sig_open_device)
        model.sig_close_mrc.connect(self.sig_close_mrc)
        model.sig_save_device_config.connect(self._slt_save_device_config)
        model.sig_load_device_config.connect(self._slt_load_device_config)
        model.sig_apply_config.connect(self._slt_apply_device_config)

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
                menu.exec_(self.mapToGlobal(pos))

    def _slt_item_doubleclicked(self, idx):
        if not (self.model().flags(idx) & Qt.ItemIsEditable):
            node = idx.internalPointer()
            if hasattr(node, 'double_clicked'):
                node.double_clicked(idx.column())

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
                cfg = config.Config()
                cfg.add_device_config(device_config)
                with open(filename, 'w') as f:
                    config_xml.write_file(cfg, f)
                device.config = device_config
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
