#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import Qt

import basic_tree_model as btm

QModelIndex = QtCore.QModelIndex

class ConfigTreeModel(btm.BasicTreeModel):
    def __init__(self, device_registry, parent=None):
        super(ConfigTreeModel, self).__init__(parent)
        self.device_registry = device_registry

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
            self._on_config_set(None, ref.cfg)

    def _on_config_set(self, old_cfg, new_cfg):
        raise NotImplementedError()

class SetupNode(ConfigTreeNode):
    def __init__(self, setup, parent=None):
        """setup should be an instance of app_model.MRCRegistry."""
        super(SetupNode, self).__init__(ref=setup, parent=parent)

    def _on_config_set(self, old_setup, new_setup):
        if old_setup is not None:
            old_setup.disconnect(self)

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

    def _on_config_set(self, old_mrc, new_mrc):
        # TODO: connect mrc signals here
        self.notify_all_columns_changed()

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            mrc = self.ref
            app_url = mrc.url
            cfg_url = mrc.cfg.url if mrc.cfg else str()
            return "app_url=%s | cfg_url=%s" % (app_url, cfg_url)

class BusNode(btm.BasicTreeNode):
    def __init__(self, bus_number, parent=None):
        super(BusNode, self).__init__(parent=parent)
        self.bus_number = bus_number

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            mrc = self.parent.ref
            if mrc.cfg:
                return str(self.bus_number)

class DeviceNode(ConfigTreeNode):
    def __init__(self, device, parent=None):
        super(DeviceNode, self).__init__(ref=device, parent=parent)

    def _on_config_set(self, old_device, new_device):
        # TODO: connect device signals here
        self.notify_all_columns_changed()

    def data(self, column, role):
        if column == 0 and role == Qt.DisplayRole:
            device = self.ref   # app_model.Device
            cfg    = device.cfg # config_model.Device

            if cfg is None:
                return "%X: <not present>" % device.address

            try:
                name = self.model.device_registry.get_device_name(cfg.idc)
                data = "%s" % name
            except KeyError:
                data = "idc=%d" % cfg.idc

            if cfg.modified:
                data += "*"

            return "%X %s" % (device.address, data)


            #return "%s %s" % (self.ref.address,
            #        self.ref.idc if self.ref is not None else "<not in config>")
            device = self.ref
            if device.cfg:
                address = device.cfg.address
                idc = device.cfg.idc
                return "%X | idc=%d | cfg=%s" % (address, idc, bool(device.cfg))
