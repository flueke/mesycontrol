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

        if ref.cfg is not None:
            self._on_config_set(ref, None, ref.cfg)

    def _on_config_set(self, app_model, old_cfg, new_cfg):
        raise NotImplementedError()

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
        if column == 0 and role == Qt.DisplayRole:
            setup = self.ref.cfg

            if len(setup):
                ret = setup.filename if len(setup.filename) else "<unsaved setup>"

                if setup.modified:
                    ret += "*"
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
        if column == 0 and role == Qt.DisplayRole:
            mrc = self.ref
            cfg = mrc.cfg

            if cfg is None:
                return "<not present in setup>"

            if len(cfg.name):
                data = "%s (%s)" % (cfg.name, mrc.get_display_url())
            else:
                data = mrc.get_display_url()

            if cfg.modified:
                data += "*"

            return data

        if column == 0 and role == Qt.EditRole:
            return self.ref.cfg.name

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

    def flags(self, column):
        if column == 0:
            ret = Qt.ItemIsEnabled | Qt.ItemIsSelectable
            if self.ref.cfg is not None:
                ret |= Qt.ItemIsEditable
            return ret

    def data(self, column, role):
        device = self.ref   # app_model.Device
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

        if role == Qt.BackgroundRole and self.model.linked_mode:
            if device.idc_conflict:
                return QtGui.QColor('red')

            if device.has_hw and device.has_cfg:
                if device.hw.is_connected() and device.config_applied:
                    return QtGui.QColor('green')
                else:
                    return QtGui.QColor('orange')

    def set_data(self, column, value, role):
        if role == Qt.EditRole and column == 0:
            self.ref.cfg.name = str(value.toString())
            return True
        return False
