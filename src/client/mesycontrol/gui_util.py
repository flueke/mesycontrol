#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import Qt
from qt import QtGui

import util

class DeviceSubWindow(QtGui.QMdiSubWindow):
    def __init__(self, widget, window_name_prefix, parent=None, **kwargs):
        super(DeviceSubWindow, self).__init__(parent)
        self.setWidget(widget)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.window_name_prefix = window_name_prefix
        self.update_title_and_name()

        self.device.config_set.connect(self._on_device_config_set)
        self._on_device_config_set(self.device, None, self.device.cfg)

    def get_device(self):
        return self.widget().device

    def get_display_mode(self):
        return self.widget().display_mode

    def set_display_mode(self, mode):
        self.widget().display_mode = mode

    def get_write_mode(self):
        return self.widget().write_mode

    def set_write_mode(self, mode):
        self.widget().write_mode = mode

    def has_combined_display(self):
        raise NotImplementedError()

    device          = property(lambda s: s.get_device())
    display_mode    = property(get_display_mode, set_display_mode)
    write_mode      = property(get_write_mode, set_write_mode)

    def update_title_and_name(self):
        """Updates the window title and the object name taking into account the
        display_mode and the device state."""
        device       = self.device
        idc          = None

        if device.hw is not None:
            idc = device.hw.idc
        elif device.cfg is not None:
            idc = device.cfg.idc

        if idc is None:
            # The device is about to disappear and this window should close. Do
            # not attempt to update the title as no idc is known and device.mrc
            # will not be set.
            return

        prefixes = {
                util.COMBINED:  'combined',
                util.HARDWARE:  'hw',
                util.CONFIG:    'cfg',
                }

        device_name = device.get_device_name()

        name = "%s_%s_(%s, %d, %d)" % (
                self.window_name_prefix, prefixes[self.display_mode],
                device.mrc.url, device.bus, device.address)

        title = "%s @ (%s, %d, %d)" % (
                device_name, device.mrc.get_display_url(),
                device.bus, device.address)

        if ((self.display_mode & util.CONFIG)
                and device.cfg is not None
                and len(device.cfg.name)):
            title = "%s - %s" % (device.cfg.name, title)

        if self.device.idc_conflict:
            title = "%s - IDC conflict" % title

        if self.device.address_conflict:
            title = "%s - address conflict" % title

        if self.device.has_cfg and self.device.cfg.modified:
            title += " *"

        self.setWindowTitle(title)
        self.setObjectName(name)

    def _on_device_config_set(self, app_device, old_cfg, new_cfg):
        signals = ['modified_changed', 'name_changed']

        if old_cfg is not None:
            for signal in signals:
                getattr(old_cfg, signal).disconnect(self.update_title_and_name)

        if new_cfg is not None:
            for signal in signals:
                getattr(new_cfg, signal).connect(self.update_title_and_name)

class DeviceWidgetSubWindow(DeviceSubWindow):
    def __init__(self, widget, parent=None):
        super(DeviceWidgetSubWindow, self).__init__(
                widget=widget, window_name_prefix='widget',
                parent=parent)

    def get_device(self):
        return self.widget().device.app_device

    def get_specialized_device(self):
        return self.widget().device

    def has_combined_display(self):
        return False

class DeviceTableSubWindow(DeviceSubWindow):
    def __init__(self, widget, parent=None):
        super(DeviceTableSubWindow, self).__init__(
                widget=widget, window_name_prefix='table',
                parent=parent)

    def has_combined_display(self):
        return True
