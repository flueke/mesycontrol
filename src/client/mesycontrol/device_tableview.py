from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import QModelIndex
from PyQt4.QtCore import Qt

from basic_model import IDCConflict
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
# => probably best to just close the window for now

# TODO: handle the case where there's no device config present yet -> create one
# TODO: handle failed sets. maybe display red background for a few seconds
# FIXME: hw device is disconnected and connected again -> hw column still says disconnected

column_titles = ('Address', 'Name', 'HW Value', 'Config Value', 'HW Unit Value', 'Config Unit Value')

# Column indexes
COL_ADDRESS, COL_NAME, COL_HW_VALUE, COL_CFG_VALUE, COL_HW_UNIT_VALUE, COL_CFG_UNIT_VALUE = range(6)



# no conflict:
#  COMBINED: show both columns; editing: write to specific col. if write mode == COMBINED: write to both
#  HARDWARE: show hw col; write to hw
#  CONFIG: show cfg col; write to cfg
# conflict:
#  COMBINED: empty table, display IDC conflict warning somewhere
#  HARDWARE: show hw values and profile and write to hw
#  CONFIG: show cfg values and profile and write to cfg
#
# => No conflict and conflict is the same for HARDWARE and CONFIG only modes.
#    COMBINED mode does differ depending on the conflict state

class DeviceTableModel(QtCore.QAbstractTableModel):
    def __init__(self, device, view_mode, write_mode, parent=None):
        super(DeviceTableModel, self).__init__(parent)
        self.log        = util.make_logging_source_adapter(__name__, self)

        self.view_mode  = view_mode
        self.write_mode = write_mode

        self._device    = None
        self.device     = device

    def set_device(self, device):
        self.beginResetModel()

        if self.device is not None:
            self.device.config_set.disconnect(self._on_device_config_set)
            self.device.hardware_set.disconnect(self._on_device_hardware_set)
            self.device.idc_conflict_changed.disconnect(self._on_device_idc_conflict_changed)

        self._device = device

        if self.device is not None:
            self.device.config_set.connect(self._on_device_config_set)
            self.device.hardware_set.connect(self._on_device_hardware_set)
            self.device.idc_conflict_changed.connect(self._on_device_idc_conflict_changed)

            self._on_device_config_set(self.device, None, self.device.cfg)
            self._on_device_hardware_set(self.device, None, self.device.hw)
            self._on_device_idc_conflict_changed(self.device.idc_conflict)

        self.endResetModel()

    def get_device(self):
        return self._device

    def get_profile(self):
        if self.view_mode == util.COMBINED:
            return self.device.get_profile()
        elif self.view_mode & util.CONFIG:
            return self.device.get_cfg_profile()
        elif self.view_mode & util.HARDWARE:
            return self.device.get_hw_profile()

    device = pyqtProperty(object, get_device, set_device)
    profile = pyqtProperty(object, get_profile)

    def _on_device_hardware_set(self, app_device, old_hw, new_hw):
        signal_slot_map = {
                'parameter_changed': self._on_hw_parameter_changed,
                'connected': self._all_fields_changed,
                'connecting': self._all_fields_changed,
                'disconnected': self._all_fields_changed,
                'connection_error': self._all_fields_changed,
                }

        if old_hw is not None:
            for signal, slot in signal_slot_map.iteritems():
                getattr(old_hw, signal).disconnect(slot)

            try:
                old_hw.remove_polling_subscriber(self)
            except KeyError:
                pass

        if new_hw is not None:
            for signal, slot in signal_slot_map.iteritems():
                getattr(new_hw, signal).connect(slot)

            for addr in app_device.profile.get_volatile_addresses():
                new_hw.add_poll_item(self, addr)

        self._all_fields_changed()

    def _on_device_config_set(self, app_device, old_cfg, new_cfg):
        if old_cfg is not None:
            old_cfg.parameter_changed.disconnect(self._on_cfg_parameter_changed)

        if new_cfg is not None:
            new_cfg.parameter_changed.connect(self._on_cfg_parameter_changed)

        self._all_fields_changed()

    def _on_device_idc_conflict_changed(self, conflict):
        if self.device.has_hw:
            self.device.hw.remove_polling_subscriber(self)
        
        if self.view_mode == util.COMBINED and conflict:
            self.beginResetModel()
            self.endResetModel()
        elif self.device.has_hw:
            for addr in self.device.get_hw_profile().get_volatile_addresses():
                self.device.hw.add_poll_item(self, addr)

    def _on_hw_parameter_changed(self, address, value):
        self.dataChanged.emit(
                self.createIndex(address, 0),
                self.createIndex(address, self.columnCount()))

    def _on_cfg_parameter_changed(self, address, value):
        self.dataChanged.emit(
                self.createIndex(address, 0),
                self.createIndex(address, self.columnCount()))

    def _all_fields_changed(self):
        self.dataChanged.emit(
                self.createIndex(0, 0),
                self.createIndex(self.rowCount(), self.columnCount()))

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
        if not idx.isValid() or self.device is None:
            return None

        row = idx.row()
        col = idx.column()
        hw  = self.device.hw
        cfg = self.device.cfg
        profile = self.device.profile

        try:
            pp = profile[row] # parameter profile
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
                if pp is None or not pp.should_be_stored():
                    return None

                if cfg is None:
                    return "<config not present>"

                try:
                    return int(cfg.get_parameter(row))
                except future.IncompleteFuture:
                    return "<reading>"
                except KeyError:
                    return "<not set>" # FIXME: editing this yiels a QLineEdit editor!

            elif col in (COL_HW_UNIT_VALUE, COL_CFG_UNIT_VALUE):
                try:
                    unit = pp.units[1] # skip the 'raw' unit at index 0
                except (IndexError, AttributeError):
                    return None

                if col == COL_HW_UNIT_VALUE and hw is not None and hw.is_connected():
                    try:
                        raw = int(hw.get_parameter(row))
                    except future.IncompleteFuture:
                        return "<reading>"

                elif col == COL_CFG_UNIT_VALUE and cfg is not None:
                    if pp is None or not pp.should_be_stored() or cfg is None:
                        return None
                    try:
                        raw = int(cfg.get_parameter(row))
                    except future.IncompleteFuture:
                        return "<reading>"
                    except KeyError:
                        return None
                else:
                    return None

                value = unit.unit_value(raw)

                return QtCore.QString.fromUtf8("%f %s" % (value, unit.label))

        if role == Qt.EditRole:
            if col == COL_HW_VALUE:
                # should succeed as otherwise the editable flag would not be set
                return int(hw.get_parameter(row))

            if col == COL_CFG_VALUE:
                try:
                # fails if no config exists or the parameter is not set
                    return int(cfg.get_parameter(row))
                except (IndexError, AttributeError, KeyError):
                    if pp is not None:
                        return pp.default
                    return 0

        if role == Qt.BackgroundRole:
            if col == COL_HW_VALUE and pp is not None and pp.read_only:
                return QtGui.QColor("lightgray")

            if col == COL_CFG_VALUE and pp is not None and not pp.should_be_stored():
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

            cfg = self.device.cfg

            if cfg is None:
                cfg = self.device.create_config()
                
            cfg.set_parameter(row, value)

            return True

class DeviceTableItemDelegate(QtGui.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(DeviceTableItemDelegate, self).__init__(parent)

    def createEditor(self, parent, options, proxy_idx):
        editor = super(DeviceTableItemDelegate, self).createEditor(parent, options, proxy_idx)

        idx = proxy_idx.model().mapToSource(proxy_idx)

        if (idx.column() in (COL_HW_VALUE, COL_CFG_VALUE)
                and isinstance(editor, QtGui.QSpinBox)):

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

        self.view_mode  = model.view_mode
        self.write_mode = model.write_mode

        try:
            print self.table_model.get_profile()
            if not len(self.profile.get_parameter_names()):
                self.setColumnHidden(COL_NAME, True)
        except IDCConflict:
            pass

    def get_view_mode(self):
        return self.table_model.view_mode

    def set_view_mode(self, mode):
        self.table_model.view_mode = mode

        self.setColumnHidden(COL_HW_VALUE, not self.does_show_hardware())
        self.setColumnHidden(COL_HW_UNIT_VALUE, not self.does_show_hardware())

        self.setColumnHidden(COL_CFG_VALUE, not self.does_show_config())
        self.setColumnHidden(COL_CFG_UNIT_VALUE, not self.does_show_config())

    def get_write_mode(self):
        return self.table_model.write_mode

    def set_write_mode(self, mode):
        self.table_model.write_mode = mode

    def does_show_hardware(self):
        return self.view_mode & util.HARDWARE

    def does_show_config(self):
        return self.view_mode & util.CONFIG

    def contextMenuEvent(self, event):
        pass

    def get_profile(self):
        return self.table_model.profile

    device = property(
            fget=lambda self: self.table_model.device,
            fset=lambda self, device: self.table_model.set_device(device))

    profile = property(
            fget=lambda self: self.table_model.profile)

    view_mode   = property(fget=get_view_mode, fset=set_view_mode)
    write_mode  = property(fget=get_write_mode, fset=set_write_mode)

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
    def __init__(self, device, view_mode=util.COMBINED, write_mode=util.COMBINED,
            parent=None):

        super(DeviceTableWidget, self).__init__(parent)

        self.log    = util.make_logging_source_adapter(__name__, self)
        settings    = util.loadUi(":/ui/device_tableview_settings.ui")

        self.log.debug("view_mode=%d, write_mode=%d", view_mode, write_mode)

        model       = DeviceTableModel(device, view_mode=view_mode, write_mode=write_mode)
        self.view   = DeviceTableView(model=model)
        sort_model  = self.view.sort_model

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
        action.triggered.connect(self.view.resizeColumnsToContents)
        action.triggered.connect(self.view.resizeRowsToContents)

        settings.pb_settings.setMenu(menu)

        settings.le_filter.textChanged.connect(sort_model.setFilterWildcard)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(settings)
        layout.addWidget(self.view)
        self.setLayout(layout)

    view_mode   = property(
            fget=lambda s: s.view.view_mode,
            fset=lambda s, v: s.view.set_view_mode(v))

    write_mode  = property(
            fget=lambda s: s.view.write_mode,
            fset=lambda s, v: s.view.set_write_mode(v))

    device      = property(
            fget=lambda s: s.view.table_model.device,
            fset =lambda s, v: s.view.table_model.set_device(v))
