#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtSignal
from qt import QtCore

import util

class Device(QtCore.QObject):
    """Acts as a decorator for an app_model.Device. Should be subclassed to
    create device specific classes, e.g. class MHV4(Device)."""
    def __init__(self, app_device, parent=None):
        super(Device, self).__init__(parent)
        self.app_device = app_device

# Parameter binding
# What's needed:
#  app_model.Device, ParameterProfile, mode (CFG or HW), widget
#
# Functionality:
#  get correct (cfg or hw depending on mode) parameter value and display it in
#  the widget
#  set the widgets tooltip
#  set the widgets limits using the ParameterProfile limits
#  react to changes to the parameter values
#  write parameter value on change to the correct destination

MODE_HW, MODE_CFG = range(2)

class ParameterBinding(QtCore.QObject):
    hw_value_changed  = pyqtSignal(object)   # address, old value, new value
    cfg_value_changed = pyqtSignal(object)   # address, old value, new value
    mode_changed      = pyqtSignal(int)             # mode

    def __init__(self, device, parameter_profile, mode, write_mode, parent=None):
        super(ParameterBinding, self).__init__(parent)
        self.device         = device
        self.profile        = parameter_profile
        self.mode           = mode
        self.write_mode     = write_mode

        self.device.hardware_set.connect(self._on_device_hw_set)
        self.device.config_set.connect(self._on_device_cfg_set)

        self._on_device_hw_set(self.device, None, self.device.hw)
        self._on_device_cfg_set(self.device, None, self.device.cfg)

    def get_address(self):
        return self.profile.address

    address = property(fget=get_address)

    def _on_device_hw_set(self, device, old_hw, new_hw):
        if old_hw is not None:
            old_hw.parameter_changed.disconnect(self._on_hw_parameter_changed)
            
        if new_hw is not None:
            new_hw.parameter_changed.connect(self._on_hw_parameter_changed)

    def _on_device_cfg_set(self, device, old_cfg, new_cfg):
        if old_cfg is not None:
            old_cfg.parameter_changed.disconnect(self._on_cfg_parameter_changed)

        if new_cfg is not None:
            new_cfg.parameter_changed.disconnect(self._on_cfg_parameter_changed)

    def _on_hw_parameter_changed(self, address, value):
        if address == self.address:
            self.hw_value_changed.emit(value)

    def _on_cfg_parameter_changed(self, address, value):
        if address == self.address:
            self.cfg_value_changed.emit(value)

DISPLAY_HW, DISPLAY_CFG = range(2)
WRITE_HW, WRITE_CFG = range(2)
WRITE_BOTH = WRITE_HW | WRITE_CFG

class ParameterUIBinding(object):
    def __init__(self, device, profile, display_mode, write_mode, widget, parent=None):
        self.device = device
        self.profile = profile
        self.display_mode = display_mode
        self.write_mode = write_mode
        self.widget = widget

        self.device.hardware_set.connect(self._on_device_hw_set)
        self.device.config_set.connect(self._on_device_cfg_set)

        self._on_device_hw_set(self.device, None, self.device.hw)
        self._on_device_cfg_set(self.device, None, self.device.cfg)

        if isinstance(self.widget, util.DelayedSpinBox):
            self.widget.delayed_valueChanged.connect(self._on_ui_value_changed)
        elif isinstance(self.widget, QtGui.SpinBox):
            self.widget.valueChanged.connect(self._on_ui_value_changed)

    def _on_device_hw_set(self, device, old_hw, new_hw):
        if old_hw is not None:
            old_hw.parameter_changed.disconnect(self._on_hw_parameter_changed)
            
        if new_hw is not None:
            new_hw.parameter_changed.connect(self._on_hw_parameter_changed)

            def on_get_done(f):
                try:
                    self._on_hw_parameter_changed(self.address, int(f))
                except Exception:
                    pass

            new_hw.get_parameter(self.address).add_done_callback(on_get_done)

    def _on_device_cfg_set(self, device, old_cfg, new_cfg):
        if old_cfg is not None:
            old_cfg.parameter_changed.disconnect(self._on_cfg_parameter_changed)

        if new_cfg is not None:
            new_cfg.parameter_changed.disconnect(self._on_cfg_parameter_changed)

    def _on_hw_parameter_changed(self, address, value):
        if address != self.address or self.display_mode != DISPLAY_HW:
            return

        self._update_widget(value)

    def _on_cfg_parameter_changed(self, address, value):
        if address != self.address or self.display_mode != DISPLAY_CFG:
            return

        self._update_widget(value)

    def _on_ui_value_changed(self, value):

        # XXX: leftoff
        def on_write_done(f):
