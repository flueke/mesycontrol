from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import uic
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import QModelIndex
from PyQt4.QtCore import Qt

import future
import basic_model as bm
import util

# TODO: handle the case where an app_model.Device goes away completely (happens
# if no config present and hardware device goes missing ->
# app_model.Device.(hw,cfg) is (None, None) -> it gets removed by the Director.
# If the device reappears after scanbus a new app_model.Device object is
# created. The table view will not know about this new object and remain in a
# "dead" state. -> close the window? store (url, bus, dev) -> window somewhere
# and update the table models device once a new device is created?

# TODO: handle the case where there's no device config present yet -> create one
# TODO: handle failed sets. maybe display red background for a few seconds

column_titles = ('Address', 'Name', 'HW Value', 'Config Value', 'HW Unit Value', 'Config Unit Value')

COL_ADDRESS, COL_NAME, COL_HW_VALUE, COL_CFG_VALUE, COL_HW_UNIT_VALUE, COL_CFG_UNIT_VALUE = range(6)

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
        return self._device

    device = pyqtProperty(object, get_device, set_device)

    def _on_device_hardware_set(self, app_device, old_hw, new_hw):
        if old_hw is not None:
            old_hw.parameter_changed.disconnect(self._on_hw_parameter_changed)
            old_hw.connected.disconnect(self._on_hw_device_connection_state_changed)
            old_hw.connecting.disconnect(self._on_hw_device_connection_state_changed)
            old_hw.disconnected.disconnect(self._on_hw_device_connection_state_changed)
            old_hw.connection_error.disconnect(self._on_hw_device_connection_state_changed)

        if new_hw is not None:
            new_hw.parameter_changed.connect(self._on_hw_parameter_changed)
            new_hw.connected.connect(self._on_hw_device_connection_state_changed)
            new_hw.connecting.connect(self._on_hw_device_connection_state_changed)
            new_hw.disconnected.connect(self._on_hw_device_connection_state_changed)
            new_hw.connection_error.connect(self._on_hw_device_connection_state_changed)

            if app_device.profile is not None:
                for addr in app_device.profile.get_volatile_addresses():
                    new_hw.add_poll_item(self, addr)

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

    def _on_hw_device_connection_state_changed(self):
        self.beginResetModel()
        self.endResetModel()

    # ===== QAbstractItemModel implementation =====
    def columnCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(column_titles)
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
        if not idx.isValid():
            return super(DeviceTableModel, self).flags(idx)

        row         = idx.row()
        col         = idx.column()
        flags       = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        hw          = self.device.hw
        try:
            pp = self.device.profile[row]
        except (IndexError, AttributeError):
            pp = None

        if (col == COL_HW_VALUE and hw is not None and hw.is_connected() and
                pp is not None and not pp.read_only and hw.has_cached_parameter(row)):
            flags |= Qt.ItemIsEditable

        if (col == COL_CFG_VALUE and pp is not None and not pp.read_only and
                not pp.do_not_store):
            flags |= Qt.ItemIsEditable

        return flags

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None

        row             = idx.row()
        col             = idx.column()

        if self.device is None:
            return None

        hw  = self.device.hw
        cfg = self.device.cfg
        profile = self.device.profile
        try:
            pp = profile[row]
        except (IndexError, AttributeError):
            pp = None

        if role == Qt.DisplayRole:
            if col == COL_ADDRESS:
                return row

            elif col == COL_NAME and pp is not None and pp.is_named():
                return pp.name

            elif col == COL_HW_VALUE:
                if hw is None or hw.is_disconnected():
                    return "<not connected>"
                if hw.is_connecting():
                    return "<connecting>"

                try:
                    return int(hw.get_parameter(row))
                except future.IncompleteFuture:
                    return "<reading>"

            elif col == COL_CFG_VALUE:
                if cfg is None:
                    return "<config not present>"

                try:
                    return int(cfg.get_parameter(row))
                except future.IncompleteFuture:
                    return "<reading>"
                except KeyError:
                    return "<not in config>"

            elif col in (COL_HW_UNIT_VALUE, COL_CFG_UNIT_VALUE):
                try:
                    unit = profile[row].units[1] # skip the 'raw' unit at index 0
                except (IndexError, AttributeError):
                    return None

                if col == COL_HW_UNIT_VALUE and hw is not None and hw.is_connected():
                    try:
                        raw = int(hw.get_parameter(row))
                    except future.IncompleteFuture:
                        return "<reading>"

                elif col == COL_CFG_UNIT_VALUE and cfg is not None:
                    raw = int(cfg.get_parameter(row))

                else:
                    return None

                value = unit.unit_value(raw)

                return QtCore.QString.fromUtf8("%f %s" % (value, unit.label))

        if role == Qt.EditRole:
            if col == COL_HW_VALUE:
                return int(hw.get_parameter(row))
            if col == COL_CFG_VALUE:
                return int(cfg.get_parameter(row))

        if role == Qt.BackgroundRole:
            if col in (COL_HW_VALUE, COL_CFG_VALUE) and (
                    pp is None or pp.read_only or pp.do_not_store):
                return QtGui.QColor("lightgray")
        return None

    def setData(self, idx, value, role = Qt.EditRole):
        if role != Qt.EditRole:
            return False

        row             = idx.row()
        col             = idx.column()

        if col == COL_HW_VALUE:
            value, ok = value.toInt()
            if not ok:
                return False

            self.device.hw.set_parameter(row, value)

            return True

        if col == COL_CFG_VALUE:
            value, ok = value.toInt()
            if not ok:
                return False

            self.device.cfg.set_parameter(row, value)

            return True

class DeviceTableItemDelegate(QtGui.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(DeviceTableItemDelegate, self).__init__(parent)

    def createEditor(self, parent, options, proxy_idx):
        editor = super(DeviceTableItemDelegate, self).createEditor(parent, options, proxy_idx)

        idx = proxy_idx.model().mapToSource(proxy_idx)

        if idx.column() in (COL_HW_VALUE, COL_CFG_VALUE):
            min_, max_ = bm.SET_VALUE_MIN, bm.SET_VALUE_MAX

            try:
                device = idx.model().device
                pp = device.profile[idx.row()]
                if pp.range is not None:
                    min_, max_ = pp.range.to_tuple()
            except (KeyError, AttributeError):
                pass

            editor.setMinimum(min_)
            editor.setMaximum(max_)

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

        self.setFilterKeyColumn(COL_NAME)

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
        pass
        #selection_model = self.selectionModel()

        #menu = QtGui.QMenu()
        #if selection_model.hasSelection():
        #    menu.addAction("Refresh selected").triggered.connect(self._slt_refresh_selected)

        #menu.addAction("Refresh visible").triggered.connect(self._slt_refresh_visible)

        #menu.exec_(event.globalPos())

    #def _slt_refresh_selected(self):
    #    selection   = self.selectionModel().selection()
    #    indexes     = self.sort_model.mapSelectionToSource(selection).indexes()
    #    addresses   = set((idx.row() for idx in indexes))

    #    #seq_cmd     = command.SequentialCommandGroup()

    #    #for addr in addresses:
    #    #    seq_cmd.add(mrc_command.ReadParameter(self.table_model.device, addr))

    #    #seq_cmd.start()

    #def _slt_refresh_visible(self):
    #    f = lambda a: self.sort_model.filterAcceptsRow(a, QtCore.QModelIndex())
    #    addresses = filter(f, xrange(256))

    #    #seq_cmd     = command.SequentialCommandGroup()

    #    #for addr in addresses:
    #    #    seq_cmd.add(mrc_command.ReadParameter(self.table_model.device, addr))

    #    #seq_cmd.start()

# TODO: change Hide to Show to make it easier to understand which params are shown...
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
