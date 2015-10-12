#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import QtGui
from qt import Qt

import basic_tree_model as btm

QModelIndex = QtCore.QModelIndex

# TODO: handle the case where no config is present. it should be easy to create the config.

class ConfigTreeModel(btm.BasicTreeModel):
    def __init__(self, device_registry, parent=None):
        super(ConfigTreeModel, self).__init__(parent)
        self.device_registry = device_registry
        self.linked_mode = False

    def columnCount(self, parent=QModelIndex()):
        return 1

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        return None

# Node types and displayed data
# SetupNode     filename, modified (*); <unsaved setup> if not filename
# MRCNode       name, url
# BusNode       bus number
# DeviceNode    address, name, type, 

class ConfigTreeNode(btm.BasicTreeNode):
    def __init__(self, ref, parent):
        super(ConfigTreeNode, self).__init__(ref=ref, parent=parent)
        ref.config_set.connect(self._on_config_set)
        ref.hardware_set.connect(self._on_hardware_set)

        if ref.cfg is not None:
            self._on_config_set(ref, None, ref.cfg)

        if ref.hw is not None:
            self._on_hardware_set(ref, None, ref.hw)

    def _on_config_set(self, app_model, old_cfg, new_cfg):
        raise NotImplementedError()

    def _on_hardware_set(self, app_model, old_hw, new_hw):
        pass

class SetupNode(ConfigTreeNode):
    def __init__(self, setup, parent=None):
        """setup should be an instance of app_model.MRCRegistry."""
        super(SetupNode, self).__init__(ref=setup, parent=parent)

    def _on_config_set(self, app_setup, old_setup, new_setup):
        if old_setup is not None:
            old_setup.filename_changed.disconnect(self.notify_all_columns_changed)
            old_setup.modified_changed.disconnect(self.notify_all_columns_changed)
            old_setup.mrc_added.disconnect(self.notify_all_columns_changed)
            old_setup.mrc_removed.disconnect(self.notify_all_columns_changed)

        if new_setup is not None:
            new_setup.filename_changed.connect(self.notify_all_columns_changed)
            new_setup.modified_changed.connect(self.notify_all_columns_changed)
            new_setup.mrc_added.connect(self.notify_all_columns_changed)
            new_setup.mrc_removed.connect(self.notify_all_columns_changed)

        self.notify_all_columns_changed()

    def data(self, column, role):
        if column == 0 and role in (Qt.DisplayRole, Qt.ToolTipRole, Qt.StatusTipRole):
            setup = self.ref.cfg

            if len(setup):
                ret = setup.filename if len(setup.filename) else "<unsaved setup>"

                if role == Qt.DisplayRole:
                    if setup.modified:
                        ret += "*"

                elif role in (Qt.ToolTipRole, Qt.StatusTipRole):
                    ret = "Setup " + ret
                    if setup.modified:
                        ret += "(modified)"

                return ret

            return "<empty setup>"

class MRCNode(ConfigTreeNode):
    def __init__(self, mrc, parent=None):
        """mrc should be an instance of app_model.MRC"""
        super(MRCNode, self).__init__(ref=mrc, parent=parent)

    def _on_config_set(self, app_mrc, old_mrc, new_mrc):
        if old_mrc is not None:
            old_mrc.name_changed.disconnect(self.notify_all_columns_changed)
            old_mrc.modified_changed.disconnect(self.notify_all_columns_changed)

        if new_mrc is not None:
            new_mrc.name_changed.connect(self.notify_all_columns_changed)
            new_mrc.modified_changed.connect(self.notify_all_columns_changed)

        self.notify_all_columns_changed()

    def flags(self, column):
        if column == 0:
            ret = Qt.ItemIsEnabled | Qt.ItemIsSelectable
            if self.ref.cfg is not None:
                ret |= Qt.ItemIsEditable
            return ret

    def data(self, column, role):
        mrc = self.ref
        cfg = mrc.cfg

        if column == 0 and role == Qt.DisplayRole:
            if cfg is None:
                return "<not present in setup>"

            if len(cfg.name):
                data = "%s (%s)" % (cfg.name, mrc.get_display_url())
            else:
                data = mrc.get_display_url()

            if cfg.modified:
                data += "*"

            return data

        if column == 0 and role in (Qt.ToolTipRole, Qt.StatusTipRole):
            ret = "MRC %s" % mrc.get_display_url()
            if cfg is not None and cfg.modified:
                ret += " (modified)"
            return ret

        if column == 0 and role == Qt.EditRole:
            return cfg.name

    def set_data(self, column, value, role):
        if role == Qt.EditRole and column == 0:
            self.ref.cfg.name = str(value.toString())
            return True
        return False

class BusNode(btm.BasicTreeNode):
    def __init__(self, bus_number, parent=None):
        super(BusNode, self).__init__(parent=parent)
        self.bus_number = bus_number

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            return str(self.bus_number)

        if column == 0 and role in (Qt.ToolTipRole, Qt.StatusTipRole):
            return "Bus %d" % self.bus_number

class DeviceNode(ConfigTreeNode):
    def __init__(self, device, parent=None):
        super(DeviceNode, self).__init__(ref=device, parent=parent)
        device.idc_conflict_changed.connect(self.notify_all_columns_changed)
        device.config_applied_changed.connect(self.notify_all_columns_changed)

    def _on_config_set(self, app_device, old_device, new_device):
        if old_device is not None:
            old_device.name_changed.disconnect(self.notify_all_columns_changed)
            old_device.modified_changed.disconnect(self.notify_all_columns_changed)

        if new_device is not None:
            new_device.name_changed.connect(self.notify_all_columns_changed)
            new_device.modified_changed.connect(self.notify_all_columns_changed)

        self.notify_all_columns_changed()

    def _on_hardware_set(self, app_device, old_hw, new_hw):
        if old_hw is not None:
            old_hw.address_conflict_changed.disconnect(self.notify_all_columns_changed)

        if new_hw is not None:
            new_hw.address_conflict_changed.connect(self.notify_all_columns_changed)

    def flags(self, column):
        if column == 0:
            ret = Qt.ItemIsEnabled | Qt.ItemIsSelectable
            if self.ref.cfg is not None:
                ret |= Qt.ItemIsEditable
            return ret

    def data(self, column, role):
        device = self.ref   # app_model.Device
        hw     = device.hw  # hardware_model.Device
        cfg    = device.cfg # config_model.Device

        if column == 0 and role == Qt.DisplayRole:

            if cfg is None:
                return "%X <not present in setup>" % device.address

            try:
                type_name = self.model.device_registry.get_device_name(cfg.idc)
            except KeyError:
                type_name = "idc=%d" % cfg.idc

            if len(cfg.name):
                data = "%s (%s)" % (cfg.name, type_name)
            else:
                data = type_name

            if cfg.modified:
                data += "*"

            return "%X %s" % (device.address, data)

        if column == 0 and role == Qt.EditRole:
            return self.ref.cfg.name

        if column == 0:
            if hw is not None and cfg is not None and self.model.linked_mode and hw.address_conflict:
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

            if cfg is not None and role in (Qt.ToolTipRole, Qt.StatusTipRole):
                data = str()
                if len(cfg.name):
                    data += cfg.name + " "

                type_name = self.model.device_registry.get_device_name(cfg.idc)
                data += "%s (idc=%d)" % (type_name, cfg.idc)

                if cfg.modified:
                    data += " (modified)"

                return data

        if role == Qt.BackgroundRole and self.model.linked_mode:
            if device.idc_conflict or device.address_conflict:
                return QtGui.QColor('red')

            if device.has_hw and device.has_cfg:
                if device.hw.is_connected():
                    if device.config_applied is True:
                        return QtGui.QColor('green')
                    if device.config_applied is False:
                        return QtGui.QColor('orange')
                    # else config_applied should be None meaning "unknown"

    def set_data(self, column, value, role):
        if role == Qt.EditRole and column == 0:
            self.ref.cfg.name = str(value.toString())
            return True
        return False
