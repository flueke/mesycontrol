from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import uic
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import QModelIndex
from PyQt4.QtCore import Qt
import weakref

import future
import basic_model as bm
import util

column_names  = ('address', 'name', 'hw_value', 'cfg_value', 'hw_unit_value', 'cfg_unit_value')
column_titles = ('Address', 'Name', 'HW Value', 'Config Value', 'HW Unit Value', 'Config Unit Value')

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
        self._device = None
        self.device = device

    def set_device(self, device):
        self.beginResetModel()
        if self.device is not None:
            self.device.config_set.disconnect(self._on_device_config_set)
            self.device.hardware_set.disconnect(self._on_device_hardware_set)

        self._device = device

        if self.device is not None:
            self.device.config_set.connect(self._on_device_config_set)
            self.device.hardware_set.connect(self._on_device_hardware_set)
            self._on_device_config_set(self.device, None, self.device.cfg)
            self._on_device_hardware_set(self.device, None, self.device.hw)
        self.endResetModel()

    def get_device(self):
        #return self._device() if self._device is not None else None
        return self._device

    device = pyqtProperty(object, get_device, set_device)

    def _on_device_hardware_set(self, app_device, old_hw, new_hw):
        if old_hw is not None:
            old_hw.parameter_changed.disconnect(self._on_hw_parameter_changed)
        if new_hw is not None:
            new_hw.parameter_changed.connect(self._on_hw_parameter_changed)

        self.beginResetModel()
        self.endResetModel()

    def _on_device_config_set(self, app_device, old_cfg, new_cfg):
        if old_cfg is not None:
            old_cfg.parameter_changed.disconnect(self._on_cfg_parameter_changed)
        if new_cfg is not None:
            new_cfg.parameter_changed.connect(self._on_cfg_parameter_changed)

        self.beginResetModel()
        self.endResetModel()

    def _on_hw_parameter_changed(self, address, value):
        self.dataChanged.emit(
                self.createIndex(address, 0),
                self.createIndex(address, self.columnCount()))

    def _on_cfg_parameter_changed(self, address, value):
        self.dataChanged.emit(
                self.createIndex(address, 0),
                self.createIndex(address, self.columnCount()))

    # ===== QAbstractItemModel implementation =====
    def columnCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(column_names)
        return 0

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(bm.PARAM_RANGE)
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
            return (Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        return super(DeviceTableModel, self).flags(idx)


    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None

        row             = idx.row()
        col             = idx.column()
        column_name     = column_names[col]

        if self.device is None:
            return None

        hw  = self.device.hw
        cfg = self.device.cfg
        profile = self.device.profile

        if role == Qt.DisplayRole:
            if column_name == 'address':
                return row

            elif column_name == 'name':
                try:
                    pp = profile[row]
                    return pp.name
                except (KeyError, AttributeError):
                    pass

            elif column_name == 'hw_value':
                if hw is None:
                    return "<not connected>"
                try:
                    return int(hw.get_parameter(row))
                except future.IncompleteFuture:
                    return "<reading>"

            elif column_name == 'cfg_value':
                if cfg is None:
                    return "<not in config>"

                try:
                    return int(cfg.get_parameter(row))
                except future.IncompleteFuture:
                    return "<reading>"
                except KeyError:
                    return "<not in config>"

            elif column_name in ('hw_unit_value', 'cfg_unit_value'):
                try:
                    raw   = int(hw.get_parameter(row) if column_name == 'hw_unit_value' else cfg.get_parameter(row))
                    unit  = profile[row].units[1] # skip the 'raw' unit at index 0
                    value = unit.unit_value(raw)
                    return QtCore.QString.fromUtf8("%f %s" % (value, unit.label))
                except Exception:
                    pass

        return None


        #if (self.device is not None
        #        and self.device.config is not None
        #        and self.device.config.contains_parameter(row)):
        #    param_config = self.device.config.get_parameter(row)

        #if (self.device is not None
        #        and self.device.profile is not None):
        #    param_profile = self.device.profile.get_parameter_by_address(row)

        #if (role == Qt.BackgroundRole
        #        and column_name in ('value', 'set_value')
        #        and self.device is not None
        #        and self.device.has_parameter(row)
        #        and param_config is not None
        #        and self.get_value(row) != param_config.value):
        #    return QtGui.QColor("#ff0000")

        #if role in (Qt.DisplayRole, Qt.EditRole):
        #    if column_name == 'address':
        #        return row
        #    elif column_name == 'value':
        #        return self.get_value(row)
        #    elif column_name == 'name':
        #        if role == Qt.DisplayRole:
        #            return param_profile.name if param_profile is not None else None
        #        return param_profile.name if param_profile is not None else str()
        #    elif column_name == 'alias':
        #        if role == Qt.DisplayRole:
        #            return param_config.alias if param_config is not None else None
        #        return param_config.alias if param_config is not None else str()
        #    elif column_name == 'set_value':
        #        if param_config is not None:
        #            return param_config.value
        #        elif self.get_value(row) is not None:
        #            return self.get_value(row)
        #        elif role == Qt.EditRole:
        #            return int()
        #    elif param_profile is not None and len(param_profile.units) > 1 and column_name == 'unit_value':
        #        unit = param_profile.units[1] # skip the 'raw' unit
        #        raw_value = self.get_value(row)
        #        if raw_value is None:
        #            return None
        #        unit_value = unit.unit_value(raw_value)
        #        return QtCore.QString.fromUtf8("%f %s" % (unit_value, unit.label))

        #return None

    #def setData(self, idx, value, role = Qt.EditRole):
    #    if role != Qt.EditRole:
    #        return False

    #    if self.device is None:
    #        return False

    #    row             = idx.row()
    #    col             = idx.column()
    #    column_name     = column_names[col]

    #    if column_name == 'set_value':
    #        int_value, ok = value.toInt()
    #        if not ok:
    #            return False

    #        self.device.set_parameter(row, int_value)

    #        self.dataChanged.emit(
    #                self.createIndex(row, 0),
    #                self.createIndex(row, self.columnCount()))

    #        return True

    #    return False

class DeviceTableItemDelegate(QtGui.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(DeviceTableItemDelegate, self).__init__(parent)

    def createEditor(self, parent, options, idx):
        editor = super(DeviceTableItemDelegate, self).createEditor(parent, options, idx)

        if column_name(idx.column()) in ('hw_value', 'cfg_value'):
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
        self._filter_unknown    = True
        self._filter_readonly   = False
        self._filter_volatile   = False
        self._filter_static     = False

        self.setFilterKeyColumn(column_index('name'))

    def set_filter_unknown(self, on_off):
        """If enabled any unknown parameter addresses are filtered out.
        `Unknown' means that the devices DeviceProfile does not contain the
        address.
        """
        self._filter_unknown = on_off
        self.invalidateFilter()

    def get_filter_unknown(self):
        return self._filter_unknown

    def set_filter_readonly(self, on_off):
        self._filter_readonly = on_off
        self.invalidateFilter()

    def get_filter_readonly(self):
        return self._filter_readonly

    def set_filter_volatile(self, on_off):
        self._filter_volatile = on_off
        self.invalidateFilter()

    def get_filter_volatile(self):
        return self._filter_volatile

    def set_filter_static(self, on_off):
        self._filter_static = on_off
        self.invalidateFilter()

    def get_filter_static(self):
        return self._filter_static

    def filterAcceptsRow(self, src_row, src_parent):
        device  = self.sourceModel().device
        profile = device.profile[src_row]

        if self.filter_unknown and profile is None:
            return False

        if self.filter_readonly and profile is not None and profile.read_only:
            return False

        if self.filter_volatile and profile is not None and profile.poll:
            return False

        if self.filter_static and profile is not None and not profile.poll:
            return False

        return super(DeviceTableSortFilterProxyModel, self).filterAcceptsRow(src_row, src_parent)

    filter_unknown  = pyqtProperty(bool, get_filter_unknown, set_filter_unknown)
    filter_readonly = pyqtProperty(bool, get_filter_readonly, set_filter_readonly)
    filter_volatile = pyqtProperty(bool, get_filter_volatile, set_filter_volatile)
    filter_static   = pyqtProperty(bool, get_filter_static, set_filter_static)

class DeviceTableView(QtGui.QTableView):
    def __init__(self, model, parent=None):
        super(DeviceTableView, self).__init__(parent)
        self.table_model = model
        self.sort_model  = DeviceTableSortFilterProxyModel(self)
        self.sort_model.setSourceModel(model)
        self.sort_model.setDynamicSortFilter(True)
        self.setModel(self.sort_model)

        model.modelReset.connect(self.resizeColumnsToContents)
        model.modelReset.connect(self.resizeRowsToContents)

        self.verticalHeader().hide()
        self.horizontalHeader().setMovable(True)
        self.sortByColumn(0, Qt.AscendingOrder)
        self.setSortingEnabled(True)
        self.setItemDelegate(DeviceTableItemDelegate())
        self.setMouseTracking(True)
        self.setWordWrap(False)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()

    def contextMenuEvent(self, event):
        selection_model = self.selectionModel()

        menu = QtGui.QMenu()
        if selection_model.hasSelection():
            menu.addAction("Refresh selected").triggered.connect(self._slt_refresh_selected)

        menu.addAction("Refresh visible").triggered.connect(self._slt_refresh_visible)

        menu.exec_(event.globalPos())

    def _slt_refresh_selected(self):
        selection   = self.selectionModel().selection()
        indexes     = self.sort_model.mapSelectionToSource(selection).indexes()
        addresses   = set((idx.row() for idx in indexes))

        #seq_cmd     = command.SequentialCommandGroup()

        #for addr in addresses:
        #    seq_cmd.add(mrc_command.ReadParameter(self.table_model.device, addr))

        #seq_cmd.start()

    def _slt_refresh_visible(self):
        f = lambda a: self.sort_model.filterAcceptsRow(a, QtCore.QModelIndex())
        addresses = filter(f, xrange(256))

        #seq_cmd     = command.SequentialCommandGroup()

        #for addr in addresses:
        #    seq_cmd.add(mrc_command.ReadParameter(self.table_model.device, addr))

        #seq_cmd.start()

class DeviceTableWidget(QtGui.QWidget):
    def __init__(self, device, find_data_file, parent=None):
        super(DeviceTableWidget, self).__init__(parent)

        settings   = uic.loadUi(find_data_file(
            'mesycontrol/ui/device_tableview_settings.ui'))
        view       = DeviceTableView(DeviceTableModel(device))
        sort_model = view.sort_model

        menu   = QtGui.QMenu('Filter options', self)
        action = menu.addAction("Hide unknown")
        action.setCheckable(True)
        action.setChecked(sort_model.filter_unknown)
        action.triggered.connect(sort_model.set_filter_unknown)

        action = menu.addAction("Hide read-only")
        action.setCheckable(True)
        action.setChecked(sort_model.filter_readonly)
        action.triggered.connect(sort_model.set_filter_readonly)

        action = menu.addAction("Hide volatile")
        action.setCheckable(True)
        action.setChecked(sort_model.filter_volatile)
        action.triggered.connect(sort_model.set_filter_volatile)

        action = menu.addAction("Hide static")
        action.setCheckable(True)
        action.setChecked(sort_model.filter_static)
        action.triggered.connect(sort_model.set_filter_static)

        menu.addSeparator()

        action = menu.addAction("Resize table cells")
        action.triggered.connect(view.resizeColumnsToContents)
        action.triggered.connect(view.resizeRowsToContents)

        settings.pb_settings.setMenu(menu)

        settings.le_filter.textChanged.connect(sort_model.setFilterWildcard)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(settings)
        layout.addWidget(view)
        self.setLayout(layout)
