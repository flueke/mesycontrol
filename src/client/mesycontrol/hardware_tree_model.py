#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import QtGui
from qt import Qt

import basic_tree_model as btm

QModelIndex = QtCore.QModelIndex

class HardwareTreeModel(btm.BasicTreeModel):
    def __init__(self, device_registry, find_data_file, parent=None):
        super(HardwareTreeModel, self).__init__(parent)
        self.find_data_file = find_data_file
        self.device_registry = device_registry

    def columnCount(self, parent=QModelIndex()):
        return 1

    def headerData(self, section, orientation, role=Qt.DisplayRole):
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
            app_url = mrc.url
            hw_url  = mrc.hw.url if mrc.hw else str()
            return "app_url=%s | hw_url=%s" % (app_url, hw_url)

        if column == 0 and role == Qt.DecorationRole:
            if mrc.hw is None:
                return None
            if not mrc.hw.is_connected() and mrc.hw.last_connection_error is not None:
                return QtGui.QPixmap(self.model.find_data_file('mesycontrol/ui/warning-2x.png'))
            elif mrc.hw.is_connecting():
                return QtGui.QPixmap(self.model.find_data_file('mesycontrol/ui/loop-circular-2x.png'))
            elif mrc.hw.is_disconnected():
                return QtGui.QPixmap(self.model.find_data_file('mesycontrol/ui/bolt-2x.png'))
            elif mrc.hw.is_connected():
                return QtGui.QPixmap(self.model.find_data_file('mesycontrol/ui/check-2x.png'))

class BusNode(btm.BasicTreeNode):
    def __init__(self, bus_number, parent=None):
        super(BusNode, self).__init__(parent=parent)
        self.bus_number = bus_number

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            return str(self.bus_number)

        if column == 0 and role == Qt.DecorationRole:
            mrc = self.parent.ref.hw
            if mrc is not None and any(device.address_conflict for device in mrc.get_devices(self.bus_number)):
                return QtGui.QPixmap(self.model.find_data_file('mesycontrol/ui/warning-2x.png'))

class DeviceNode(HardwareTreeNode):
    def __init__(self, device, parent=None):
        super(DeviceNode, self).__init__(ref=device, parent=parent)

    def _on_hardware_set(self, app_device, old_device, new_device):
        # TODO: connect device signals
        self.notify_all_columns_changed()

    def data(self, column, role):
        device  = self.ref   # app_model.Device
        hw      = device.hw  # hardware_model.Device
        mrc     = device.mrc # app_model.MRC

        if column == 0 and role == Qt.DisplayRole:
            if hw is None:
                return "%X <not present>" % device.address

            try:
                name = self.model.device_registry.get_device_name(hw.idc)
                data = "%s" % name
            except KeyError:
                data = "idc=%d" % hw.idc

            return "%X %s" % (device.address, data)

        if column == 0 and role == Qt.DecorationRole:
            if hw is not None and hw.address_conflict:
                return QtGui.QPixmap(self.model.find_data_file('mesycontrol/ui/warning-2x.png'))

            if hw is None or mrc.hw is None:
                return None
            if not mrc.hw.is_connected() and mrc.hw.last_connection_error is not None:
                return QtGui.QPixmap(self.model.find_data_file('mesycontrol/ui/warning-2x.png'))
            elif mrc.hw.is_connecting():
                return QtGui.QPixmap(self.model.find_data_file('mesycontrol/ui/loop-circular-2x.png'))
            elif mrc.hw.is_disconnected():
                return QtGui.QPixmap(self.model.find_data_file('mesycontrol/ui/bolt-2x.png'))
            elif mrc.hw.is_connected():
                return QtGui.QPixmap(self.model.find_data_file('mesycontrol/ui/check-2x.png'))
