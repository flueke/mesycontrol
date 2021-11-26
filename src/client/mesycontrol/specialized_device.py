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

from mesycontrol.qt import Property
from mesycontrol.qt import Signal
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtWidgets
from mesycontrol.qt import Qt

import mesycontrol.future as future
import mesycontrol.gui_util as gui_util
import mesycontrol.util as util

class DeviceBase(QtCore.QObject):
    """Acts as a decorator for an app_model.Device. Should be subclassed to
    create device specific classes, e.g. class MHV4(DeviceBase)."""

    mrc_changed             = Signal(object)

    hardware_set            = Signal(object, object, object) #: self, old, new
    config_set              = Signal(object, object, object) #: self, old, new

    idc_conflict_changed    = Signal(bool)
    idc_changed             = Signal(int)
    hw_idc_changed          = Signal(int)
    cfg_idc_changed         = Signal(int)

    module_changed          = Signal(object)
    hw_module_changed       = Signal(object)
    cfg_module_changed      = Signal(object)

    profile_changed         = Signal(object)
    hw_profile_changed      = Signal(object)
    cfg_profile_changed     = Signal(object)

    config_applied_changed  = Signal(object)

    read_mode_changed       = Signal(object)
    write_mode_changed      = Signal(object)

    parameter_changed       = Signal(int, object)
    extension_changed       = Signal(str, object)

    def __init__(self, app_device, read_mode, write_mode, parent=None):
        """
        app_device: app_model.Device
        read_mode:  util.HARDWARE | util.CONFIG
        write_mode: util.HARDWARE | util.CONFIG | util.COMBINED
        """

        super(DeviceBase, self).__init__(parent)

        self.log = util.make_logging_source_adapter(__name__, self)

        self.log.debug("DeviceBase(d=%s, r_mode=%s, w_mode=%s)",
                app_device,
                util.RW_MODE_NAMES[read_mode],
                util.RW_MODE_NAMES[write_mode])

        self.app_device = app_device
        self.app_device.mrc_changed.connect(self.mrc_changed)

        self.app_device.hardware_set.connect(self._on_hardware_set)
        self.app_device.config_set.connect(self._on_config_set)

        self.app_device.idc_conflict_changed.connect(self.idc_conflict_changed)
        self.app_device.idc_changed.connect(self.idc_changed)
        self.app_device.hw_idc_changed.connect(self.hw_idc_changed)
        self.app_device.cfg_idc_changed.connect(self.cfg_idc_changed)

        self.app_device.module_changed.connect(self.module_changed)
        self.app_device.hw_module_changed.connect(self.hw_module_changed)
        self.app_device.cfg_module_changed.connect(self.cfg_module_changed)

        self.app_device.profile_changed.connect(self.profile_changed)
        self.app_device.hw_profile_changed.connect(self.hw_profile_changed)
        self.app_device.cfg_profile_changed.connect(self.cfg_profile_changed)

        self.app_device.config_applied_changed.connect(self.config_applied_changed)

        self.app_device.hw_parameter_changed.connect(self._on_hw_parameter_changed)
        self.app_device.cfg_parameter_changed.connect(self._on_cfg_parameter_changed)

        self.app_device.hw_extension_changed.connect(self._on_hw_extension_changed)
        self.app_device.cfg_extension_changed.connect(self._on_cfg_extension_changed)

        self._read_mode  = read_mode
        self._write_mode = write_mode

    def get_read_mode(self):
        return self._read_mode

    def set_read_mode(self, mode):
        if mode != self.read_mode:
            self._read_mode = mode
            self.read_mode_changed.emit(self.read_mode)

    def get_write_mode(self):
        return self._write_mode

    def set_write_mode(self, mode):
        if mode != self.write_mode:
            self._write_mode = mode
            self.write_mode_changed.emit(self.write_mode)

    def __getattr__(self, attr):
        """Forward attribute access to the app_model.Device instance."""
        return getattr(self.app_device, attr)

    read_mode       = Property(object, get_read_mode, set_read_mode, notify=read_mode_changed)
    write_mode      = Property(object, get_write_mode, set_write_mode, notify=write_mode_changed)
    idc_conflict    = Property(bool, lambda s: s.has_idc_conflict(), notify=idc_conflict_changed)

    # ===== mode dependent =====
    def get_parameter(self, address_or_name):
        address = self.profile[address_or_name].address
        dev = self.hw if self.read_mode == util.HARDWARE else self.cfg
        return dev.get_parameter(address)

    def set_parameter(self, address_or_name, value):
        address = self.profile[address_or_name].address

        if self.write_mode == util.COMBINED:

            ret = future.Future()

            def on_hw_write_done(f):
                try:
                    if f.exception() is not None:
                        ret.set_exception(f.exception())
                    else:
                        ret.set_result(f.result())
                except future.CancelledError:
                    ret.cancel()

            def on_cfg_write_done(f):
                try:
                    if f.exception() is not None:
                        ret.set_exception(f.exception())
                    else:
                        self.hw.set_parameter(address, value
                                ).add_done_callback(on_hw_write_done)
                except future.CancelledError:
                    ret.cancel()

            self.cfg.set_parameter(address, value
                    ).add_done_callback(on_cfg_write_done)

            return ret

        dev = self.hw if self.write_mode == util.HARDWARE else self.cfg
        return dev.set_parameter(address, value)

    def get_extension(self, name):
        dev = self.hw if self.read_mode == util.HARDWARE else self.cfg
        return dev.get_extension(name)

    def set_extension(self, name, value):
        self.log.debug("set_extension: name=%s, value=%s", name, value)
        if self.write_mode == util.COMBINED:
            self.cfg.set_extension(name, value)
            self.hw.set_extension(name, value)
        else:
            dev = self.hw if self.write_mode == util.HARDWARE else self.cfg
            dev.set_extension(name, value)

    def get_extensions(self):
        dev = self.hw if self.read_mode == util.HARDWARE else self.cfg
        return dev.get_extensions()

    def get_module(self):
        return self.cfg_module if self.read_mode & util.CONFIG else self.hw_module

    module = property(fget=get_module)

    def get_profile(self):
        return self.module.profile

    profile = property(fget=get_profile)

    # ===== HW =====
    def get_hw_parameter(self, address_or_name):
        address = self.profile[address_or_name].address
        return self.hw.get_parameter(address)

    def read_hw_parameter(self, address_or_name):
        address = self.profile[address_or_name].address
        return self.hw.read_parameter(address)

    def set_hw_parameter(self, address_or_name, value):
        address = self.profile[address_or_name].address
        return self.hw.set_parameter(address, value)

    def _on_hardware_set(self, app_device, old, new):
        self.hardware_set.emit(self, old, new)

    def _on_hw_parameter_changed(self, address, value):
        if self.read_mode & util.HARDWARE:
            self.parameter_changed.emit(address, value)

    def _on_hw_extension_changed(self, name, value):
        if self.read_mode & util.HARDWARE:
            self.extension_changed.emit(name, value)

    # ===== CFG =====
    def get_cfg_parameter(self, address_or_name):
        address = self.profile[address_or_name].address
        return self.cfg.get_parameter(address)

    def read_cfg_parameter(self, address_or_name):
        address = self.profile[address_or_name].address
        return self.cfg.read_parameter(address)

    def set_cfg_parameter(self, address_or_name, value):
        address = self.profile[address_or_name].address
        return self.cfg.set_parameter(address, value)

    def _on_config_set(self, app_device, old, new):
        self.config_set.emit(self, old, new)

    def _on_cfg_parameter_changed(self, address, value):
        if self.read_mode & util.CONFIG:
            self.parameter_changed.emit(address, value)

    def _on_cfg_extension_changed(self, name, value):
        if self.read_mode & util.CONFIG:
            self.extension_changed.emit(name, value)

    def get_display_string(self):
        return "{mrc},{self.bus},{self.address} {devicename}".format(
                devicename=self.profile.name,
                mrc=self.mrc.get_display_url(),
                self=self)

class DeviceWidgetBase(QtWidgets.QWidget):
    """Base class for device specific widgets."""
    display_mode_changed = Signal(int)
    write_mode_changed   = Signal(int)
    hardware_connected_changed = Signal(bool)

    def __init__(self, specialized_device, display_mode, write_mode, parent=None):
        """Construct a device specific widget.
        * specialized_device should be a DeviceBase subclass tailored to the specific device.
        * display_mode and write_mode are the display and write modes to use with the device.
        """
        super(DeviceWidgetBase, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.device = specialized_device
        self._display_mode = display_mode
        self._write_mode   = write_mode
        self.make_settings = None

        self.device.hardware_set.connect(self._on_device_hardware_set)
        self._on_device_hardware_set(self.device, None, self.device.hw)

        self.notes_widget = gui_util.DeviceNotesWidget(specialized_device)

        self.hide_notes_button = QtWidgets.QPushButton(clicked=self._toggle_hide_notes)
        self.set_notes_visible(False)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setCornerWidget(self.hide_notes_button, Qt.TopRightCorner)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.notes_widget)
        layout.addWidget(self.tab_widget)
        layout.setStretch(1, 1)

    def _toggle_hide_notes(self):
        self.set_notes_visible(not self.notes_visible())

    def notes_visible(self):
        return self.notes_widget.isVisible()

    def set_notes_visible(self, visible):
        self.notes_widget.setVisible(visible)

        if visible:
            self.hide_notes_button.setIcon(util.make_icon(":/collapse-up.png"))
            self.hide_notes_button.setToolTip("Hide Device notes")
        else:
            self.hide_notes_button.setIcon(util.make_icon(":/collapse-down.png"))
            self.hide_notes_button.setToolTip("Show Device notes")

        self.hide_notes_button.setStatusTip(self.hide_notes_button.toolTip())

    def get_display_mode(self):
        return self.device.read_mode

    def set_display_mode(self, display_mode):
        if self.device.read_mode == display_mode:
            return

        self.device.read_mode = display_mode

        for binding in self.get_parameter_bindings():
            binding.display_mode = display_mode

        self.display_mode_changed.emit(self.display_mode)

        if self.write_mode != util.COMBINED:
            self.write_mode = self.display_mode

    def get_write_mode(self):
        return self.device.write_mode

    def set_write_mode(self, write_mode):
        if self.device.write_mode == write_mode:
            return

        self.device.write_mode = write_mode

        for binding in self.get_parameter_bindings():
            binding.write_mode = write_mode

        self.write_mode_changed.emit(self.write_mode)

        if write_mode != util.COMBINED:
            self.display_mode = self.write_mode

    display_mode = Property(
            object,
            fget=lambda s: s.get_display_mode(),
            fset=lambda s,v: s.set_display_mode(v),
            notify=display_mode_changed)

    write_mode   = Property(
            object,
            fget=lambda s: s.get_write_mode(),
            fset=lambda s, v: s.set_write_mode(v),
            notify=write_mode_changed)

    def get_parameter_bindings(self):
        raise NotImplementedError()

    def clear_parameter_bindings(self):
        raise NotImplementedError()

    def has_toolbar(self):
        return len(self.actions())

    def get_toolbar(self):
        tb = QtWidgets.QToolBar()

        for a in self.actions():
            tb.addAction(a)

        return tb

    def showEvent(self, event):
        if not event.spontaneous():

            for binding in self.get_parameter_bindings():
                binding.populate()

            self.log.debug("showEvent: has_hw=%s, display_mode & HW=%s, idc_conflict=%s",
                    self.device.has_hw, self.display_mode & util.HARDWARE, self.device.idc_conflict)

            if (self.device.has_hw and
                    ((self.display_mode & util.HARDWARE)
                        or not self.device.idc_conflict)):
                self.log.debug("showEvent: adding default poll subscription")
                self.device.add_default_polling_subscription(self)

        super(DeviceWidgetBase, self).showEvent(event)

    def closeEvent(self, event):
        if (self.parent()
                and len(self.parent().objectName())
                and self.make_settings):
            settings = self.make_settings()
            name = "DeviceWidgets/%s_notes_visible" % self.parent().objectName()
            settings.setValue(name, self.notes_visible())

        self.clear_parameter_bindings()
        super(DeviceWidgetBase, self).closeEvent(event)

    def event(self, e):
        if (e.type() == QtCore.QEvent.Polish
                and self.parent()
                and len(self.parent().objectName())
                and self.make_settings):

            settings = self.make_settings()
            name = "DeviceWidgets/%s_notes_visible" % self.parent().objectName()
            if settings.contains(name):
                self.set_notes_visible(bool(settings.value(name)))
            else:
                self.set_notes_visible(False)

        return super(DeviceWidgetBase, self).event(e)

    def _on_device_hardware_set(self, device, old, new):
        self.log.debug("_on_device_hardware_set: device=%s, old=%s, new=%s",
                device, old, new)

        if old is not None:
            self.log.debug("_on_device_hardware_set: removing old poll subscription")
            old.remove_polling_subscriber(self)
            old.connected.disconnect(self._on_hardware_connected)
            old.disconnected.disconnect(self._on_hardware_disconnected)

        if new is not None:
            if ((self.display_mode & util.HARDWARE) or not self.device.idc_conflict):
                self.log.debug("_on_device_hardware_set: adding default poll subscription")
                self.device.add_default_polling_subscription(self)
            new.connected.connect(self._on_hardware_connected)
            new.disconnected.connect(self._on_hardware_disconnected)

    def _on_hardware_connected(self):

        if ((self.display_mode & util.HARDWARE) or not self.device.idc_conflict):
            self.log.debug("_on_hardware_connected: adding default poll subscription")
            self.device.add_default_polling_subscription(self)

        self.hardware_connected_changed.emit(True)

    def _on_hardware_disconnected(self):
        self.hardware_connected_changed.emit(False)
