#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtProperty
from qt import pyqtSignal
from qt import QtCore
from qt import QtGui
from qt import Qt

import future
import util

class DeviceBase(QtCore.QObject):
    """Acts as a decorator for an app_model.Device. Should be subclassed to
    create device specific classes, e.g. class MHV4(DeviceBase)."""

    mrc_changed             = pyqtSignal(object)

    hardware_set            = pyqtSignal(object, object, object) #: self, old, new
    config_set              = pyqtSignal(object, object, object) #: self, old, new

    idc_conflict_changed    = pyqtSignal(bool)
    idc_changed             = pyqtSignal(int)
    hw_idc_changed          = pyqtSignal(int)
    cfg_idc_changed         = pyqtSignal(int)

    module_changed          = pyqtSignal(object)
    hw_module_changed       = pyqtSignal(object)
    cfg_module_changed      = pyqtSignal(object)

    profile_changed         = pyqtSignal(object)
    hw_profile_changed      = pyqtSignal(object)
    cfg_profile_changed     = pyqtSignal(object)

    config_applied_changed  = pyqtSignal(object)

    read_mode_changed       = pyqtSignal(object)
    write_mode_changed      = pyqtSignal(object)

    parameter_changed       = pyqtSignal(int, object)
    extension_changed       = pyqtSignal(str, object)

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
        return getattr(self.app_device, attr)

    read_mode       = pyqtProperty(object, get_read_mode, set_read_mode, notify=read_mode_changed)
    write_mode      = pyqtProperty(object, get_write_mode, set_write_mode, notify=write_mode_changed)
    idc_conflict    = pyqtProperty(bool, lambda s: s.has_idc_conflict(), notify=idc_conflict_changed)

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
        dev = self.hw if self.write_mode == util.HARDWARE else self.cfg
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
        dev = self.hw if self.write_mode == util.HARDWARE else self.cfg
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

class DeviceWidgetBase(QtGui.QWidget):
    display_mode_changed = pyqtSignal(int)
    write_mode_changed   = pyqtSignal(int)
    hardware_connected_changed = pyqtSignal(bool)

    def __init__(self, specialized_device, display_mode, write_mode, parent=None):
        super(DeviceWidgetBase, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.device = specialized_device
        self._display_mode = display_mode
        self._write_mode   = write_mode

        self.device.hardware_set.connect(self._on_device_hardware_set)
        self._on_device_hardware_set(self.device, None, self.device.hw)

        self.addAction(QtGui.QAction(
            util.make_icon(":/device-notes.png"),
            "Device Notes", self,
            triggered=self._edit_device_notes))

        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tab_widget = QtGui.QTabWidget()
        layout.addWidget(self.tab_widget)

    def add_widget_tab(self, widget):
        self.tab_widget.addTab(widget, "Widget")

    def get_display_mode(self):
        return self.device.read_mode

    def set_display_mode(self, display_mode):
        self.device.read_mode = display_mode

        for binding in self.get_parameter_bindings():
            binding.display_mode = display_mode

        self.display_mode_changed.emit(self.display_mode)

    def get_write_mode(self):
        return self.device.write_mode

    def set_write_mode(self, write_mode):
        self.device.write_mode = write_mode

        for binding in self.get_parameter_bindings():
            binding.write_mode = write_mode

        self.write_mode_changed.emit(self.write_mode)

    display_mode = property(
            fget=lambda s: s.get_display_mode(),
            fset=lambda s,v: s.set_display_mode(v))

    write_mode   = property(
            fget=lambda s: s.get_write_mode(),
            fset=lambda s, v: s.set_write_mode(v))

    def get_parameter_bindings(self):
        raise NotImplementedError()

    def has_toolbar(self):
        return len(self.actions())

    def get_toolbar(self):
        tb = QtGui.QToolBar()

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

    def _edit_device_notes(self):
        d = DeviceNotesDialog(self.device, self)
        d.show()

class DeviceNotesDialog(QtGui.QDialog):
    def __init__(self, device, parent=None):
        super(DeviceNotesDialog, self).__init__(parent)

        self._text_edit  = QtGui.QPlainTextEdit()
        self._button_box = QtGui.QDialogButtonBox(
                QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Discard)

        l = QtGui.QVBoxLayout(self)
        l.addWidget(self._text_edit)
        l.addWidget(self._button_box)
