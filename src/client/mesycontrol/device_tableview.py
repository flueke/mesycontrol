from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import QModelIndex
from PyQt4.QtCore import Qt
import weakref

import app_model
import mrc_command
import util

column_names  = ('address', 'name', 'value', 'set_value', 'unit_value')
column_titles = ('Address', 'Name', 'Raw Value', 'Set Raw Value', 'Unit Value')

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

class ParameterNode(util.TreeNode):
    data_changed = pyqtSignal()

    def __init__(self, device, address, parent):
        super(ParameterNode, self).__init__(device, parent)
        self.address = address
        self._read_request_id = None

        device.parameter_changed.connect(self._on_parameter_changed)
        device.config_parameter_value_changed.connect(self._on_config_parameter_changed)

    def _on_parameter_changed(self, address, old, new):
        if self.address == address:
            self.data_changed.emit()

    def _on_config_parameter_changed(self, address, value):
        if self.address == address:
            self.data_changed.emit()

    def flags(self, column):
        ret = (Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        if column_names[column] in ('set_value',):
            ret |= Qt.ItemIsEditable

        return ret

    def get_value(self):
        if not self.ref.has_parameter(self.address):
            if self._read_request_id is None and self.ref.is_connected():
                self._read_request_id = self.ref.read_parameter(self.address, self._handle_read_response)
            return None
        return self.ref.get_parameter(self.address)

    def _handle_read_response(self, request, response):
        self._read_request_id = None

    def get_config(self):
        if self.ref.config is not None and self.ref.config.contains_parameter(self.address):
            return self.ref.config.get_parameter(self.address)
        return None

    def get_profile(self):
        if self.ref.profile is not None:
            return self.ref.profile.get_parameter_by_address(self.address)
        return None

    def data(self, column, role):
        param_config  = self.get_config()
        param_profile = self.get_profile()
        column_name   = column_names[column]

        if (role == Qt.BackgroundRole
                and column_name in ('value', 'set_value')
                and self.ref.has_parameter(self.address)
                and self.get_config() is not None
                and self.get_value() != self.get_config().value):
            return QtGui.QColor("#ff0000")

        if role in (Qt.DisplayRole, Qt.EditRole):
            if column_name == 'address':
                return self.address
            elif column_name == 'value':
                return self.get_value()
            elif column_name == 'name':
                if role == Qt.DisplayRole:
                    return param_profile.name if param_profile is not None else None
                return param_profile.name if param_profile is not None else str()
            elif column_name == 'alias':
                if role == Qt.DisplayRole:
                    return param_config.alias if param_config is not None else None
                return param_config.alias if param_config is not None else str()
            elif column_name == 'set_value':
                if param_config is not None:
                    return param_config.value
                elif self.get_value() is not None:
                    return self.get_value()
                elif role == Qt.EditRole:
                    return int()
            elif param_profile is not None and len(param_profile.units) > 1 and column_name == 'unit_value':
                unit = param_profile.units[1] # skip the 'raw' unit
                raw_value = self.get_value()
                if raw_value is None:
                    return None
                unit_value = unit.unit_value(raw_value)
                return QtCore.QString.fromUtf8("%f %s" % (unit_value, unit.label))

        return None
            

    def set_data(self, column, value, role):
        if role != Qt.EditRole:
            return False

        column_name  = column_names[column]

        if column_name == 'set_value':
            int_value, ok = value.toInt()
            if not ok:
                return False
            mrc_command.SetParameter(self.ref, self.address, int_value).start()
            param_config = self.get_config()
            if param_config is not None:
                param_config.value = int_value
            return True
        return False

    def context_menu(self, column):
        ret = QtGui.QMenu()
        ret.addAction("Refresh").triggered.connect(self._slt_refresh)
        ret.addAction("Refresh All").triggered.connect(self._slt_refresh_all)
        return ret

    def _slt_refresh(self):
        mrc_command.ReadParameter(self.ref, self.address).start()

    def _slt_refresh_all(self):
        mrc_command.RefreshMemory(self.ref).start()

class DeviceTableModel(QtCore.QAbstractTableModel):
    def __init__(self, device, parent=None):
        super(DeviceTableModel, self).__init__(parent)
        self.root   = util.TreeNode(None)
        self.device = device

    def set_device(self, device):
        self.beginResetModel()

        for parameter_node in self.root.children:
            parameter_node.setParent(None)

        self.root.children = list()

        for i in range(256):
            parameter_node = ParameterNode(device, i, self.root)
            parameter_node.data_changed.connect(self._on_parameter_node_changed)
            self.root.children.append(parameter_node)

        self._device = weakref.ref(device)

        device.memory_reset.connect(self._reset_model)

        self.endResetModel()

    def get_device(self):
        return self._device()

    def get_node(self, row):
        return self.root.children[row]

    device = pyqtProperty(app_model.Device, get_device, set_device)

    def _on_parameter_node_changed(self):
        address = self.sender().address
        idx1 = self.createIndex(address, 0, self.root)
        idx2 = self.createIndex(address, self.columnCount(), self.root)
        self.dataChanged.emit(idx1, idx2)

    def _reset_model(self):
        self.beginResetModel()
        self.endResetModel()


    # ===== QAbstractItemModel implementation =====
    def columnCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(column_names)
        return 0

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(self.root.children)
        return 0

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            try:
                return column_titles[section]
            except IndexError:
                return None
        elif orientation == Qt.Vertical and role == Qt.DisplayRole:
            return section
        return None

    def flags(self, idx):
        ret = None
        if idx.isValid():
            try:
                ret = self.root.children[idx.row()].flags(idx.column())
            except NotImplementedError:
                pass
        return ret if ret is not None else super(DeviceTableModel, self).flags(idx)

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None
        return self.root.children[idx.row()].data(idx.column(), role)

    def setData(self, idx, value, role = Qt.EditRole):
        ret = False
        if idx.isValid():
            try:
                ret = self.root.children[idx.row()].set_data(idx.column(), value, role)
            except NotImplementedError:
                pass
        if ret:
            self.dataChanged.emit(
                    self.index(idx.row(), 0),
                    self.index(idx.row(), self.columnCount()))
        return ret

class DeviceTableItemDelegate(QtGui.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(DeviceTableItemDelegate, self).__init__(parent)

    def createEditor(self, parent, options, idx):
        editor = super(DeviceTableItemDelegate, self).createEditor(parent, options, idx)

        if column_name(idx.column()) == 'set_value':
            editor.setMinimum(0)
            editor.setMaximum(65535)

        return editor

class DeviceTableSortFilterProxyModel(QtGui.QSortFilterProxyModel):
    """QSortFilterProxyModel subclass to be used with the DeviceTableView.
    Filtering capabilities:
      * known addresses
      * read / write addresses
      * addresses with the poll flag set
    """
    def __init__(self, parent=None):
        super(DeviceTableSortFilterProxyModel, self).__init__(parent)
        self._filter_unknown   = False
        self._filter_read_only = False

    def set_filter_unknown(self, on_off):
        """If enabled any unknown parameter addresses are hidden. `Unknown'
        means that the devices DeviceProfile does not contain the address.
        """
        self._filter_unknown = on_off
        self.invalidateFilter()

    def get_filter_unknown(self):
        return self._filter_unknown

    def set_filter_read_only(self, on_off):
        self._filter_read_only = on_off
        self.invalidateFilter()

    def get_filter_read_only(self):
        return self._filter_read_only

class DeviceTableView(QtGui.QTableView):
    def __init__(self, model, parent=None):
        super(DeviceTableView, self).__init__(parent)
        self.table_model = model
        self.sort_model  = QtGui.QSortFilterProxyModel(self)
        self.sort_model.setSourceModel(model)
        self.sort_model.setDynamicSortFilter(True)
        self.setModel(self.sort_model)

        model.modelReset.connect(self.resizeColumnsToContents)
        model.modelReset.connect(self.resizeRowsToContents)

        self.verticalHeader().hide()
        self.horizontalHeader().setMovable(True)
        self.sortByColumn(0, Qt.AscendingOrder)
        self.setSortingEnabled(True)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.doubleClicked.connect(self._on_item_doubleclicked)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._slt_context_menu_requested)
        self.setMouseTracking(True)
        self.setItemDelegate(DeviceTableItemDelegate())

    def _on_item_doubleclicked(self, idx):
        idx = self.sort_model.mapToSource(idx)
        print "click on", idx.row(), idx.column(), idx.internalPointer()
        if self.model().flags(idx) & Qt.ItemIsEditable:
            print 'editable'

    def _slt_context_menu_requested(self, pos):
        idx = self.sort_model.mapToSource(self.indexAt(pos))

        if idx.isValid():
            node = self.table_model.get_node(idx.row())
            print node
            menu = node.context_menu(idx.column())
            print menu
            if menu is not None:
                menu.exec_(self.mapToGlobal(pos))
