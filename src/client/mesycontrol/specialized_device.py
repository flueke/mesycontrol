#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtProperty
from qt import pyqtSignal
from qt import QtCore

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

    def __init__(self, app_device, read_mode, write_mode, parent=None):
        """
        app_device: app_model.Device
        read_mode:  util.HARDWARE | util.CONFIG
        write_mode: util.HARDWARE | util.CONFIG | util.COMBINED
        """

        super(DeviceBase, self).__init__(parent)

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
