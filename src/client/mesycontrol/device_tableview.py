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

column_names  = ('address', 'name', 'value',     'set_value',     'unit_value')
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

class DeviceTableModel(QtCore.QAbstractTableModel):
    def __init__(self, device, parent=None):
        super(DeviceTableModel, self).__init__(parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self._pending_parameters = set()
        self.device = device

    def set_device(self, device):
        self.beginResetModel()
        self._device = weakref.ref(device)
        device.memory_reset.connect(self._reset_model)
        device.add_default_parameter_subscription(self)
        device.parameter_changed.connect(self._on_device_parameter_changed)
        device.config_parameter_value_changed.connect(self._on_device_config_parameter_changed)
        self.endResetModel()

    def get_device(self):
        return self._device()

    def _on_device_parameter_changed(self, address, old_value, value):
        self.log.debug("device param changed %d: %d -> %d", address, old_value, value)

        self.dataChanged.emit(
                self.createIndex(address, 0),
                self.createIndex(address, self.columnCount()))

    def _on_device_config_parameter_changed(self, address, value):
        self.log.debug("device config param changed %d = %d", address, value)

        self.dataChanged.emit(
                self.createIndex(address, 0),
                self.createIndex(address, self.columnCount()))

    def _reset_model(self):
        self.beginResetModel()
        self.endResetModel()

    def get_value(self, address):
        if not self.device.has_parameter(address):
            if self.device.is_connected() and address not in self._pending_parameters:
                self.log.debug("fetching param %d", address)
                self.device.read_parameter(address, self._handle_read_response)
                self._pending_parameters.add(address)
            return None
        return self.device.get_parameter(address)

    def _handle_read_response(self, request, response):
        if not response.is_error():
            self.log.debug("got param %d", response.par)
            self._pending_parameters.remove(response.par)

    device = pyqtProperty(app_model.Device, get_device, set_device)

    # ===== QAbstractItemModel implementation =====
    def columnCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(column_names)
        return 0

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return 256
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
        if idx.isValid():
            ret = (Qt.ItemIsSelectable | Qt.ItemIsEnabled)

            if column_names[idx.column()] in ('set_value',):
                ret |= Qt.ItemIsEditable

            return ret

        return super(DeviceTableModel, self).flags(idx)


    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None

        row             = idx.row()
        col             = idx.column()
        column_name     = column_names[col]
        param_config    = self.device.config.get_parameter(row) if self.device.config.contains_parameter(row) else None
        param_profile   = self.device.profile.get_parameter_by_address(row)

        if (role == Qt.BackgroundRole
                and column_name in ('value', 'set_value')
                and self.device.has_parameter(row)
                and param_config is not None
                and self.get_value(row) != param_config.value):
            return QtGui.QColor("#ff0000")

        if role in (Qt.DisplayRole, Qt.EditRole):
            if column_name == 'address':
                return row
            elif column_name == 'value':
                return self.get_value(row)
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
                elif self.get_value(row) is not None:
                    return self.get_value(row)
                elif role == Qt.EditRole:
                    return int()
            elif param_profile is not None and len(param_profile.units) > 1 and column_name == 'unit_value':
                unit = param_profile.units[1] # skip the 'raw' unit
                raw_value = self.get_value(row)
                if raw_value is None:
                    return None
                unit_value = unit.unit_value(raw_value)
                return QtCore.QString.fromUtf8("%f %s" % (unit_value, unit.label))

        return None

    def setData(self, idx, value, role = Qt.EditRole):
        if role != Qt.EditRole:
            return False

        row             = idx.row()
        col             = idx.column()
        column_name     = column_names[col]

        if column_name == 'set_value':
            int_value, ok = value.toInt()
            if not ok:
                return False

            self.device.set_parameter(row, int_value)

            self.dataChanged.emit(
                    self.createIndex(row, 0),
                    self.createIndex(row, self.columnCount()))

            return True

        return False

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

    def filterAcceptsColumn(self, src_column, src_parent):
        # XXX: leftoff
        return super(DeviceTableSortFilterProxyModel, self).filterAcceptsColumn(src_column, src_parent)

    def filterAcceptsRow(self, src_row, src_parent):
        return super(DeviceTableSortFilterProxyModel, self).filterAcceptsRow(src_row, src_parent)

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

        #if idx.isValid():
        #    node = self.table_model.get_node(idx.row())
        #    print node
        #    menu = node.context_menu(idx.column())
        #    print menu
        #    if menu is not None:
        #        menu.exec_(self.mapToGlobal(pos))
