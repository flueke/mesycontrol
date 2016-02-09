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
__email__  = 'florianlueke@gmx.net'

from qt import QtCore
from qt import QtGui
from qt import Qt

import basic_tree_model as btm

column_titles = ('Path', 'RC')

COL_PATH, COL_RC = range(2)

QModelIndex = QtCore.QModelIndex

class HardwareTreeModel(btm.BasicTreeModel):
    def __init__(self, device_registry, parent=None):
        super(HardwareTreeModel, self).__init__(parent)
        self.device_registry = device_registry
        self.linked_mode = False

    def columnCount(self, parent=QModelIndex()):
        return 2

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            try:
                return column_titles[section]
            except IndexError:
                pass
        return None

class HardwareTreeNode(btm.BasicTreeNode):
    def __init__(self, ref, parent):
        super(HardwareTreeNode, self).__init__(ref=ref, parent=parent)
        ref.hardware_set.connect(self._on_hardware_set)

        if ref.hw is not None:
            self._on_hardware_set(ref, None, ref.hw)

    def _on_hardware_set(self, app_model, old_hw, new_hw):
        raise NotImplementedError()

class RegistryNode(HardwareTreeNode):
    def __init__(self, registry, parent=None):
        """registry should be an instance of app_model.MRCRegistry."""
        super(RegistryNode, self).__init__(ref=registry, parent=parent)

    def _on_hardware_set(self, app_reg, old_reg, new_reg):
        pass # Right now the hardware registry should not change

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            return "Connections"

class MRCNode(HardwareTreeNode):
    def __init__(self, mrc, parent=None):
        """mrc should be an instance of app_model.MRC"""
        super(MRCNode, self).__init__(ref=mrc, parent=parent)

    def _on_hardware_set(self, app_mrc, old_mrc, new_mrc):
        if old_mrc is not None:
            old_mrc.connected.disconnect(self.notify_all_columns_changed)
            old_mrc.connecting.disconnect(self.notify_all_columns_changed)
            old_mrc.disconnected.disconnect(self.notify_all_columns_changed)
            old_mrc.connection_error.disconnect(self.notify_all_columns_changed)

        if new_mrc is not None:
            new_mrc.connected.connect(self.notify_all_columns_changed)
            new_mrc.connecting.connect(self.notify_all_columns_changed)
            new_mrc.disconnected.connect(self.notify_all_columns_changed)
            new_mrc.connection_error.connect(self.notify_all_columns_changed)

        self.notify_all_columns_changed()

    def data(self, column, role):
        mrc = self.ref

        if column == 0 and role == Qt.DisplayRole:
            return mrc.get_display_url()

        if column == 0:
            if mrc.hw is not None and not mrc.hw.is_connected() and mrc.hw.last_connection_error is not None:
                if role == Qt.DecorationRole:
                    return QtGui.QPixmap(":/warning.png")

                if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    return "%s: %s" % (mrc.get_display_url(), mrc.hw.last_connection_error)

            elif mrc.hw is not None and mrc.hw.is_connecting():
                if role == Qt.DecorationRole:
                    return QtGui.QPixmap(":/connecting.png")

                if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    return "Connecting to %s" % (mrc.get_display_url(),)

            elif mrc.hw is None or mrc.hw.is_disconnected():
                if role == Qt.DecorationRole:
                    return QtGui.QPixmap(":/disconnected.png")

                if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    return "Disconnected from %s" % (mrc.get_display_url(),)

            elif mrc.hw is not None and mrc.hw.is_connected() and any(d.address_conflict for d in mrc.hw):
                if role == Qt.DecorationRole:
                    return QtGui.QPixmap(":/warning.png")

                if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    return "Address conflict detected"

            elif mrc.hw is not None and mrc.hw.is_connected():
                if role == Qt.DecorationRole:
                    return QtGui.QPixmap(":/connected.png")

                if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    return "Connected to %s" % mrc.get_display_url()

class BusNode(btm.BasicTreeNode):
    def __init__(self, bus_number, parent=None):
        super(BusNode, self).__init__(parent=parent)
        self.bus_number = bus_number

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            return str(self.bus_number)

        if column == 0 and role in (Qt.ToolTipRole, Qt.StatusTipRole):
            return "Bus %d" % self.bus_number

        if column == 0 and role == Qt.DecorationRole:
            mrc = self.parent.ref.hw
            if mrc is not None and any(d.address_conflict for d in mrc.get_devices(self.bus_number)):
                return QtGui.QPixmap(":/warning.png")

class DeviceNode(HardwareTreeNode):
    def __init__(self, device, parent=None):
        super(DeviceNode, self).__init__(ref=device, parent=parent)
        device.idc_conflict_changed.connect(self.notify_all_columns_changed)
        device.config_applied_changed.connect(self.notify_all_columns_changed)

    def _on_hardware_set(self, app_device, old_device, new_device):
        signals = ['connected', 'connecting', 'disconnected', 'connection_error',
                'address_conflict_changed', 'rc_changed']

        if old_device is not None:
            for signal in signals:
                getattr(old_device, signal).disconnect(self.notify_all_columns_changed)

        if new_device is not None:
            for signal in signals:
                getattr(new_device, signal).connect(self.notify_all_columns_changed)

        self.notify_all_columns_changed()

    def flags(self, column):
        device  = self.ref   # app_model.Device
        hw      = device.hw  # hardware_model.Device
        mrc     = device.mrc # app_model.MRC

        ret = Qt.ItemIsEnabled | Qt.ItemIsSelectable

        if (column == COL_RC
                and hw is not None
                and mrc.hw.is_connected()
                and not hw.address_conflict):
            ret |= Qt.ItemIsEditable

        return ret

    def data(self, column, role):
        device  = self.ref   # app_model.Device
        hw      = device.hw  # hardware_model.Device
        mrc     = device.mrc # app_model.MRC

        if column == 0 and role == Qt.DisplayRole:
            if mrc.hw is None or not mrc.hw.is_connected():
                return "%X <no mrc connection>" % device.address
            elif hw is None:
                return "%X <device not connected>" % device.address

            try:
                name = self.model.device_registry.get_device_name(hw.idc)
                data = "%s" % name
            except KeyError:
                name = None
                data = "idc=%d" % hw.idc

            return "%X %s" % (device.address, data)

        if column == COL_RC and hw is not None and mrc.hw.is_connected():
            if role == Qt.DisplayRole:
                return "RC on" if hw.rc else "RC off"
            if role == Qt.EditRole:
                return hw.rc

        if column == 0:
            if hw is not None and hw.address_conflict:
                if role == Qt.DecorationRole:
                    return QtGui.QPixmap(":/warning.png")

                if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    return "Address conflict"

            if hw is not None and self.model.linked_mode and  device.idc_conflict:
                if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    return "IDC conflict"

            if self.model.linked_mode and device.has_hw and device.has_cfg and device.hw.is_connected():
                if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    if device.config_applied is True:
                        return "Hardware matches config"
                    elif device.config_applied is False:
                        return "Hardware and config differ"

            if mrc.hw is None or mrc.hw.is_disconnected():
                if role == Qt.DecorationRole:
                    return QtGui.QPixmap(":/disconnected.png")

                if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    return "Disconnected from %s" % (mrc.get_display_url(),)

            if mrc.hw is not None and mrc.hw.is_connecting():
                if role == Qt.DecorationRole:
                    return QtGui.QPixmap(":/connecting.png")

                if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    return "Connecting to %s" % (mrc.get_display_url(),)

            if mrc.hw is not None and mrc.hw.is_connected() and not hw:
                if role == Qt.DecorationRole:
                    return QtGui.QPixmap(":/disconnected.png")

            if mrc.hw is not None and not mrc.hw.is_connected() and mrc.hw.last_connection_error is not None:
                if role == Qt.DecorationRole:
                    return QtGui.QPixmap(":/warning.png")

                if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    return "%s: %s" % (mrc.get_display_url(), mrc.hw.last_connection_error)

            if mrc.hw is not None and mrc.hw.is_connected() and hw is not None:
                if role == Qt.DecorationRole:
                    return QtGui.QPixmap(":/connected.png")

                if role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    return "%s (idc=%d)" % (device.hw_profile.name, hw.idc)

        if role == Qt.BackgroundRole and self.model.linked_mode:
            if hw is not None and hw.address_conflict:
                return QtGui.QColor('red')

            if device.idc_conflict and self.model.linked_mode:
                return QtGui.QColor('red')

            if device.has_hw and device.has_cfg:
                if device.hw.is_connected():
                    if device.config_applied is True:
                        return QtGui.QColor('green')
                    if device.config_applied is False:
                        return QtGui.QColor('orange')
                    # else config_applied should be None meaning "unknown"

    def set_data(self, column, value, role):
        if role == Qt.EditRole and column == COL_RC:
            self.ref.hw.set_rc(value)
