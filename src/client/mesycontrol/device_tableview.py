#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2016 mesytec GmbH & Co. KG <info@mesytec.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

__author__ = 'Florian Lüke'
__email__  = 'f.lueke@mesytec.com'

from qt import pyqtProperty
from qt import pyqtSignal
from qt import Qt
from qt import QtCore
from qt import QtGui

QModelIndex = QtCore.QModelIndex

import collections

from basic_model import IDCConflict
import future
import basic_model as bm
import util

# TODO: handle the case where there's no device config present yet -> create one
# TODO: handle failed sets. maybe display red background for a few seconds

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
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(DeviceTableModel, self).__init__(parent)
        self.log        = util.make_logging_source_adapter(__name__, self)

        self._display_mode = display_mode
        self._write_mode   = write_mode

        self._device    = None
        self.device     = device
        self._editing_ignore_paramter_ranges = False

    def set_device(self, device):
        signals_slots = {
                'config_set': self._on_device_config_set,
                'hardware_set': self._on_device_hardware_set,
                'idc_conflict_changed': self._on_device_idc_conflict_changed,
                }

        self.beginResetModel()

        if self.device is not None:
            for signal, slot in signals_slots.iteritems():
                getattr(self.device, signal).disconnect(slot)

        self._device = device

        if self.device is not None:
            for signal, slot in signals_slots.iteritems():
                getattr(self.device, signal).connect(slot)

            self._on_device_config_set(self.device, None, self.device.cfg)
            self._on_device_hardware_set(self.device, None, self.device.hw)
            self._on_device_idc_conflict_changed(self.device.idc_conflict)

        self.endResetModel()

    def get_device(self):
        return self._device

    def get_profile(self):
        if self.display_mode == util.COMBINED and not self.device.idc_conflict:
            return self.device.get_profile()
        elif self.display_mode & util.CONFIG:
            return self.device.get_cfg_profile()
        elif self.display_mode & util.HARDWARE:
            return self.device.get_hw_profile()

    def set_display_mode(self, mode):
        self._display_mode = mode
        self._all_fields_changed()

    def get_display_mode(self):
        return self._display_mode

    def set_write_mode(self, mode):
        self._write_mode = mode
        self._all_fields_changed()

    def get_write_mode(self):
        return self._write_mode

    def set_editing_ignore_parameter_ranges(self, do_ignore):
        self._editing_ignore_paramter_ranges = bool(do_ignore)

    def get_editing_ignore_parameter_ranges(self):
        return self._editing_ignore_paramter_ranges

    device = pyqtProperty(object, get_device, set_device)
    profile = pyqtProperty(object, get_profile)
    display_mode = pyqtProperty(object, get_display_mode, set_display_mode)
    write_mode   = pyqtProperty(object, get_write_mode, set_write_mode)

    editing_ignore_parameter_ranges = pyqtProperty(
            bool,
            get_editing_ignore_parameter_ranges,
            set_editing_ignore_parameter_ranges)

    def _on_device_hardware_set(self, app_device, old_hw, new_hw):
        self.log.debug("_on_device_hardware_set: dev=%s, old=%s, new=%s",
                app_device, old_hw, new_hw)

        signal_slot_map = {
                'parameter_changed': self._on_hw_parameter_changed,
                'connected': self._on_hardware_connected,
                'connecting': self._all_fields_changed,
                'disconnected': self._all_fields_changed,
                'connection_error': self._all_fields_changed,
                'address_conflict_changed': self._all_fields_changed
                }

        if old_hw is not None:
            for signal, slot in signal_slot_map.iteritems():
                getattr(old_hw, signal).disconnect(slot)

            try:
                self.log.debug("_on_device_hardware_set: removing old poll subscription")
                old_hw.remove_polling_subscriber(self)
            except KeyError:
                pass

        if new_hw is not None:
            for signal, slot in signal_slot_map.iteritems():
                getattr(new_hw, signal).connect(slot)

            if new_hw.is_connected():
                self._on_hardware_connected()

        self._all_fields_changed()

    def _on_device_config_set(self, app_device, old_cfg, new_cfg):
        if old_cfg is not None:
            old_cfg.parameter_changed.disconnect(self._on_cfg_parameter_changed)

        if new_cfg is not None:
            new_cfg.parameter_changed.connect(self._on_cfg_parameter_changed)

        self._all_fields_changed()

    def _on_device_idc_conflict_changed(self, conflict):
        if self.device.has_hw:
            self.log.debug("_on_device_idc_conflict_changed: removing poll subscription")
            self.device.hw.remove_polling_subscriber(self)
        
        if self.display_mode == util.COMBINED and conflict:
            self.beginResetModel()
            self.endResetModel()
        elif (self.device.has_hw and
                ((self.display_mode & util.HARDWARE)
                    or not self.device.idc_conflict)):
            self.log.debug("_on_device_idc_conflict_changed: Adding poll subscription")
            self.device.add_default_polling_subscription(self)

    def _on_hardware_connected(self):
        if ((self.display_mode & util.HARDWARE) or not self.device.idc_conflict):
            self.log.info("_on_hardware_connected: adding poll subscription")
            self.device.add_default_polling_subscription(self)
        self._all_fields_changed()

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
            pp = self.profile[row]
        except (IndexError, AttributeError):
            pp = None

        if (col == COL_HW_VALUE
                and hw is not None
                and hw.is_connected()
                and not hw.address_conflict
                and ((pp is not None and not pp.read_only)
                    or pp is None)
                and hw.has_cached_parameter(row)):
            flags |= Qt.ItemIsEditable

        if (col == COL_CFG_VALUE
                and (pp is not None
                    and not pp.read_only
                    and not pp.do_not_store)
                or (pp is None)):
            flags |= Qt.ItemIsEditable

        return flags

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid() or self.device is None:
            return None

        row = idx.row()
        col = idx.column()
        hw  = self.device.hw
        cfg = self.device.cfg
        profile = self.profile

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
                if hw is None:
                    return "<device not present>"

                if hw.is_disconnected():
                    return "<not connected>"

                if hw.is_connecting():
                    return "<connecting>"

                if hw.address_conflict:
                    return "<address conflict>"

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
                    return "<not set>"

            elif col in (COL_HW_UNIT_VALUE, COL_CFG_UNIT_VALUE):
                try:
                    unit = pp.units[1] # skip the 'raw' unit at index 0
                except (IndexError, AttributeError):
                    return None

                if (col == COL_HW_UNIT_VALUE
                        and hw is not None
                        and hw.is_connected()
                        and not hw.address_conflict):
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
            if (self.display_mode == util.COMBINED
                    and hw is not None
                    and cfg is not None
                    and pp is not None
                    and pp.should_be_stored()):
                try:
                    cfg_raw = int(cfg.get_parameter(row))
                    hw_raw  = int(hw.get_parameter(row))
                    if cfg_raw != hw_raw:
                        return QtGui.QColor('orange')
                except (future.IncompleteFuture, KeyError,
                        util.SocketError, util.Disconnected):
                    pass

            if col == COL_HW_VALUE and pp is not None and pp.read_only:
                return QtGui.QColor("lightgray")

            if col == COL_CFG_VALUE and pp is not None and not pp.should_be_stored():
                return QtGui.QColor("lightgray")

        if role in (Qt.ToolTipRole, Qt.StatusTipRole):
            if pp is not None and pp.read_only:
                if col == COL_HW_VALUE:
                    return "%s=%s (read_only)" % (
                            pp.name if pp.is_named() else str(row),
                            self.data(idx, Qt.DisplayRole))

                if col == COL_CFG_VALUE:
                    return "%s (read_only)" % (
                            pp.name if pp.is_named() else str(row))

            if col == COL_CFG_VALUE and pp is not None and not pp.should_be_stored():
                return "%s (not stored in config)" % (
                        pp.name if pp.is_named() else str(row))

        return None

    def setData(self, idx, value, role = Qt.EditRole):
        if role != Qt.EditRole:
            return False

        row             = idx.row()
        col             = idx.column()
        value, ok       = value.toInt()

        if not ok:
            return False

        try:
            if col == COL_HW_VALUE:
                def set_cfg(f):
                    if not f.exception() and self.write_mode == util.COMBINED:
                        self.device.cfg.set_parameter(row, value)

                self.device.hw.set_parameter(row, value).add_done_callback(set_cfg)
                return True

            if col == COL_CFG_VALUE:
                if not self.device.has_cfg:
                    self.device.create_config()

                cfg = self.device.cfg

                def set_hw(f):
                    if (not f.exception()
                            and self.write_mode == util.COMBINED
                            and self.device.has_hw):
                        self.device.hw.set_parameter(row, value)

                cfg.set_parameter(row, value).add_done_callback(set_hw)

                return True
        except Exception:
            self.log.exception("Error setting parameter %d to %d on %s",
                    row, value, self.device)
            return False

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
                #device = idx.model().device
                #pp = device.profile[idx.row()]
                profile = idx.model().profile
                pp = profile[idx.row()]
                if (pp.range is not None
                        and not idx.model().get_editing_ignore_parameter_ranges()):
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
        profile = self.sourceModel().profile[src_row]

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
    display_mode_changed = pyqtSignal(int)
    write_mode_changed   = pyqtSignal(int)

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
        self.setSelectionMode(QtGui.QAbstractItemView.ContiguousSelection)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()

        self.display_mode   = model.display_mode
        self.write_mode     = model.write_mode

        self._actions = collections.OrderedDict()
        self._toolbar = None
        self._clipboard = QtGui.QApplication.clipboard()

        self._create_actions()

        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

        try:
            if not len(self.profile.get_parameter_names()):
                self.setColumnHidden(COL_NAME, True)
        except IDCConflict:
            pass

    def _create_actions(self):
        a = QtGui.QAction(QtGui.QIcon.fromTheme("edit-copy"), "&Copy", self,
                triggered=self._copy_action)

        a.setShortcut(QtGui.QKeySequence.Copy)
        a.setEnabled(False)
        self._actions['copy'] = a

        a = QtGui.QAction(QtGui.QIcon.fromTheme("edit-paste"), "&Paste", self,
                triggered=self._paste_action)
        a.setShortcut(QtGui.QKeySequence.Paste)
        a.setEnabled(False)
        self._actions['paste'] = a

    def get_display_mode(self):
        return self.table_model.display_mode

    def set_display_mode(self, mode):
        self.table_model.display_mode = mode

        self.setColumnHidden(COL_HW_VALUE, not self.does_show_hardware())
        self.setColumnHidden(COL_HW_UNIT_VALUE, not self.does_show_hardware())

        self.setColumnHidden(COL_CFG_VALUE, not self.does_show_config())
        self.setColumnHidden(COL_CFG_UNIT_VALUE, not self.does_show_config())

        self.display_mode_changed.emit(self.display_mode)

    def get_write_mode(self):
        return self.table_model.write_mode

    def set_write_mode(self, mode):
        self.table_model.write_mode = mode
        self.write_mode_changed.emit(self.write_mode)

    def does_show_hardware(self):
        return self.display_mode & util.HARDWARE

    def does_show_config(self):
        return self.display_mode & util.CONFIG

    def contextMenuEvent(self, event):
        menu = QtGui.QMenu()

        for a in self._actions.itervalues():
            if a.isEnabled():
                menu.addAction(a)

        if not menu.isEmpty():
            menu.exec_(self.mapToGlobal(event.pos()))

    def get_profile(self):
        return self.table_model.profile

    device = property(
            fget=lambda self: self.table_model.device,
            fset=lambda self, device: self.table_model.set_device(device))

    profile = property(
            fget=lambda self: self.table_model.profile)

    display_mode   = property(fget=get_display_mode, fset=set_display_mode)
    write_mode  = property(fget=get_write_mode, fset=set_write_mode)

    def get_toolbar(self):
        if self._toolbar is None:
            self._toolbar = tb = QtGui.QToolBar()
            for a in self._actions.values():
                tb.addAction(a)
        return self._toolbar

    def _has_selection(self):
        return self.selectionModel().hasSelection()

    def _get_selected_indexes(self):
        return sorted(self.sort_model.mapSelectionToSource(
            self.selectionModel().selection()).indexes())

    def _on_selection_changed(self, selected, deselected):
        self._actions['copy'].setEnabled(self._has_selection())
        self._actions['paste'].setEnabled(False)

        if self._has_selection():
            selected = self._get_selected_indexes()
            col0     = selected[0].column()

            self._actions['paste'].setEnabled(
                    self._clipboard.mimeData().hasText() and
                    col0 in (COL_HW_VALUE, COL_CFG_VALUE) and
                    (not self.isColumnHidden(col0)) and
                    all((idx.column() == col0 for idx in selected)))

    def _copy_action(self):
        selected = self._get_selected_indexes()
        row = selected[0].row()
        row_data = list()
        row_data.append(list())

        for idx in selected:
            if self.isColumnHidden(idx.column()):
                continue

            if idx.row() != row:
                row_data.append(list())
                row = idx.row()

            row_data[-1].append(unicode(self.table_model.data(idx)))

        text  = '\n'.join(['\t'.join(s) for s in row_data])

        self._clipboard.setText(text)

    def _paste_action(self):
        selected = self._get_selected_indexes()
        row, col = selected[0].row(), selected[0].column()
        values = str(self._clipboard.text()).split('\n')
        try:
            values = [int(value) for value in values]
        except ValueError:
            return

        for value in values:
            min_, max_ = bm.SET_VALUE_MIN, bm.SET_VALUE_MAX

            try:
                pp = self.profile[row]
                if pp.range is not None:
                    min_, max_ = pp.range.to_tuple()
            except (KeyError, AttributeError):
                pass

            idx = self.table_model.index(row, col)

            if min_ <= value <= max_ and self.table_model.flags(idx) & Qt.ItemIsEditable:
                self.table_model.setData(idx, QtCore.QVariant(value))

            row += 1

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
    display_mode_changed = pyqtSignal(int)
    write_mode_changed   = pyqtSignal(int)

    def __init__(self, device, display_mode=util.COMBINED, write_mode=util.COMBINED,
            parent=None):

        super(DeviceTableWidget, self).__init__(parent)

        self.log    = util.make_logging_source_adapter(__name__, self)
        settings    = util.loadUi(":/ui/device_tableview_settings.ui")

        self.log.debug("display_mode=%d, write_mode=%d", display_mode, write_mode)

        model       = DeviceTableModel(device, display_mode=display_mode, write_mode=write_mode)
        self.view   = DeviceTableView(model=model)
        sort_model  = self.view.sort_model

        self.view.display_mode_changed.connect(self.display_mode_changed)
        self.view.write_mode_changed.connect(self.write_mode_changed)

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

        action = menu.addAction("Ignore param ranges on edit")
        action.setCheckable(True)
        action.triggered.connect(model.set_editing_ignore_parameter_ranges)

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

    def get_toolbar(self):
        return self.view.get_toolbar()

    display_mode   = property(
            fget=lambda s: s.view.display_mode,
            fset=lambda s, v: s.view.set_display_mode(v))

    write_mode  = property(
            fget=lambda s: s.view.write_mode,
            fset=lambda s, v: s.view.set_write_mode(v))

    device      = property(
            fget=lambda s: s.view.table_model.device,
            fset =lambda s, v: s.view.table_model.set_device(v))
