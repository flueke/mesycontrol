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

from mesycontrol.qt import QtWidgets
from mesycontrol.qt import Signal

from mesycontrol import config_util
import mesycontrol.hardware_controller
import mesycontrol.util

QMB = QtWidgets.QMessageBox

def std_button_to_cfg_action(button):
    d = {
            QMB.Retry:      config_util.ACTION_RETRY,
            QMB.Ignore:     config_util.ACTION_SKIP,
            QMB.Abort:      config_util.ACTION_ABORT,
            QMB.Yes:        config_util.ACTION_YES,
            QMB.YesToAll:   config_util.ACTION_YES_TO_ALL,
            QMB.No:         config_util.ACTION_NO,
            QMB.NoToAll:    config_util.ACTION_NO_TO_ALL,
            }
    if button in d:
        return d[button]

    raise ValueError("unknown button %d" % button)

class SubProgressDialog(QtWidgets.QDialog):
    canceled = Signal()

    def __init__(self, title=str(), parent=None):
        super(SubProgressDialog, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        util.loadUi(":/ui/subprogress_widget.ui", self)
        self.setWindowTitle(title)
        self.cancel_button.clicked.connect(self.cancel)
        self._reset()

    def _reset(self):
        for label in (self.progress_label, self.subprogress_label):
            label.setText(str())

        for bar in (self.progressbar, self.subprogressbar):
            bar.setMinimum(0)
            bar.setMaximum(100)
            bar.setValue(0)

    def set_progress(self, progress):
        self.log.debug("set_progress: %s", progress)
        self.progress_label.setText(progress.text)
        self.progressbar.setMaximum(progress.total)
        self.progressbar.setValue(progress.current)

        if hasattr(progress, 'subprogress'):
            subprogress = progress.subprogress
            self.subprogress_label.setText(subprogress.text)
            self.subprogressbar.setMaximum(subprogress.total)
            self.subprogressbar.setValue(subprogress.current)

    def cancel(self):
        self.hide()
        self._reset()
        self.canceled.emit()

class ApplySetupRunner(config_util.GeneratorRunner):
    progress_changed = Signal(object)

    def __init__(self, app_registry, device_registry, parent_widget, parent=None):
        super(ApplySetupRunner, self).__init__(parent=parent)

        self.log             = util.make_logging_source_adapter(__name__, self)
        self.app_registry    = app_registry
        self.device_registry = device_registry
        self.parent_widget   = parent_widget

    def _start(self):
        self.generator = config_util.connect_and_apply_setup(self.app_registry, self.device_registry)

    def _object_yielded(self, obj):
        if isinstance(obj, hardware_controller.TimeoutError):

            answer = QMB.question(
                    self.parent_widget,
                    "Connection error",
                    "Timeout connecting to %s" % obj.args[0],
                    buttons=QMB.Retry | QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Retry)

            return (std_button_to_cfg_action(answer), False)

        if isinstance(obj, config_util.MissingDestinationDevice):

            answer = QMB.question(
                    self.parent_widget,
                    "Missing Device",
                    "No device at %s, %d, %d" % (util.display_url(obj.url), obj.bus, obj.dev),
                    buttons=QMB.Retry | QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Retry)

            return (std_button_to_cfg_action(answer), False)

        if isinstance(obj, config_util.IDCConflict):
            answer = QMB.question(
                    self.parent_widget,
                    "IDC Conflict",
                    str(obj),
                    buttons=QMB.Retry | QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Retry)

            return (std_button_to_cfg_action(answer), False)

        if isinstance(obj, config_util.SetParameterError):
            url  = obj.url
            bus  = obj.set_result.bus
            dev  = obj.set_result.device
            addr = obj.set_result.address

            try:
                device = self.app_registry.get_mrc(url).get_device(bus, dev)
                param_name = device.profile[addr].name
                param_name = "'%s' (address=%d)" % (param_name, addr)
            except KeyError:
                param_name = "address=%d" % (addr)

            msg = "Error setting %s to %d. Result: %d" % (
                    param_name, obj.set_result.requested_value, obj.set_result.value)

            answer = QMB.question(
                    self.parent_widget,
                    "Set parameter error",
                    msg,
                    buttons=QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Abort)

            return (std_button_to_cfg_action(answer), False)

        raise ValueError("Error: %s" % obj)

    def _progress_update(self, progress):
        super(ApplySetupRunner, self)._progress_update(progress)
        self.progress_changed.emit(progress)

class ApplyDeviceConfigRunner(config_util.GeneratorRunner):
    def __init__(self, device, parent_widget, parent=None):
        super(ApplyDeviceConfigRunner, self).__init__(parent=parent)

        self.log = util.make_logging_source_adapter(__name__, self)
        self.device = device
        self.parent_widget = parent_widget

    def _start(self):
        self.generator = config_util.apply_device_config(self.device)

    def _object_yielded(self, obj):
        if isinstance(obj, config_util.SetParameterError):
            set_result = obj.set_result

            try:
                param_name = self.device.profile[set_result.address].name
                param_name = "'%s' (address=%d)" % (param_name, set_result.address)
            except KeyError:
                param_name = "address=%d" % (set_result.address,)

            msg = "Error setting %s to %d. Result: %d" % (
                    param_name, set_result.requested_value, set_result.value)

            answer = QMB.question(
                    self.parent_widget,
                    "Set parameter error",
                    msg,
                    buttons=QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Abort)

            return (std_button_to_cfg_action(answer), False)

class ApplyDeviceConfigsRunner(config_util.GeneratorRunner):
    progress_changed = Signal(object)

    def __init__(self, devices, parent_widget, parent=None):
        super(ApplyDeviceConfigsRunner, self).__init__(parent=parent)

        self.devices = devices
        self.parent_widget = parent_widget

    def _start(self):
        self.generator = config_util.apply_device_configs(self.devices)

    def _object_yielded(self, obj):
        if isinstance(obj, config_util.SetParameterError):
            set_result = obj.set_result
            device     = obj.device

            try:
                param_name = device.profile[set_result.address].name
                param_name = "'%s' (address=%d)" % (param_name, set_result.address)
            except KeyError:
                param_name = "address=%d" % (set_result.address,)

            msg = "(%s, %d, %d): Error setting %s to %d. Result: %d" % (
                    device.mrc.get_display_url(), device.bus, device.address,
                    param_name, set_result.requested_value, set_result.value)

            answer = QMB.question(
                    self.parent_widget,
                    "Set parameter error",
                    msg,
                    buttons=QMB.Retry | QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Abort)

            return (std_button_to_cfg_action(answer), False)

        if isinstance(obj, hardware_controller.TimeoutError):

            answer = QMB.question(
                    self.parent_widget,
                    "Connection error",
                    "Timeout connecting to %s" % obj.args[0],
                    buttons=QMB.Retry | QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Retry)

            return (std_button_to_cfg_action(answer), False)

        if isinstance(obj, config_util.MissingDestinationDevice):

            answer = QMB.question(
                    self.parent_widget,
                    "Missing Device",
                    "No device at %s, %d, %d" % (util.display_url(obj.url), obj.bus, obj.dev),
                    buttons=QMB.Retry | QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Retry)

            return (std_button_to_cfg_action(answer), False)

        if isinstance(obj, config_util.IDCConflict):
            answer = QMB.question(
                    self.parent_widget,
                    "IDC Conflict",
                    str(obj),
                    buttons=QMB.Retry | QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Retry)

            return (std_button_to_cfg_action(answer), False)

        if isinstance(obj, config_util.RcOff):
            device = obj.device

            s = "%s @ (%s, %d, %X)" % (
                    device.get_device_name(),
                    device.mrc.get_display_url(),
                    device.bus, device.address)

            answer = QMB.question(
                    self.parent_widget,
                    "RC setting",
                    "RC is disabled for %s.\nDo you want to enable RC now?" % s,
                    buttons=QMB.No | QMB.NoToAll | QMB.Yes | QMB.YesToAll | QMB.Abort,
                    defaultButton=QMB.Yes)

            return (std_button_to_cfg_action(answer), False)

        raise ValueError("Error: %s" % obj)

    def _progress_update(self, progress):
        super(ApplyDeviceConfigsRunner, self)._progress_update(progress)
        self.progress_changed.emit(progress)

class FillDeviceConfigsRunner(config_util.GeneratorRunner):
    progress_changed = Signal(object)

    def __init__(self, devices, parent_widget, parent=None):
        super(FillDeviceConfigsRunner, self).__init__(parent=parent)

        self.devices = devices
        self.parent_widget = parent_widget

    def _start(self):
        self.generator = config_util.fill_device_configs(self.devices)

    def _object_yielded(self, obj):
        if isinstance(obj, config_util.SetParameterError):
            set_result = obj.set_result
            device     = obj.device

            try:
                param_name = device.profile[set_result.address].name
                param_name = "'%s' (address=%d)" % (param_name, set_result.address)
            except KeyError:
                param_name = "address=%d" % (set_result.address,)

            msg = "(%s, %d, %d): Error setting %s to %d. Result: %d" % (
                    device.mrc.get_display_url(), device.bus, device.address,
                    param_name, set_result.requested_value, set_result.value)

            answer = QMB.question(
                    self.parent_widget,
                    "Set parameter error",
                    msg,
                    buttons=QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Abort)

            return (std_button_to_cfg_action(answer), False)

        if isinstance(obj, hardware_controller.TimeoutError):

            answer = QMB.question(
                    self.parent_widget,
                    "Connection error",
                    "Timeout connecting to %s" % obj.args[0],
                    buttons=QMB.Retry | QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Retry)

            return (std_button_to_cfg_action(answer), False)

        if isinstance(obj, config_util.MissingDestinationDevice):

            answer = QMB.question(
                    self.parent_widget,
                    "Missing Device",
                    "No device at %s, %d, %d" % (util.display_url(obj.url), obj.bus, obj.dev),
                    buttons=QMB.Retry | QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Retry)

            return (std_button_to_cfg_action(answer), False)

        if isinstance(obj, config_util.IDCConflict):
            answer = QMB.question(
                    self.parent_widget,
                    "IDC Conflict",
                    str(obj),
                    buttons=QMB.Retry | QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Retry)

            return (std_button_to_cfg_action(answer), False)

        raise ValueError("Error: %s" % obj)

    def _progress_update(self, progress):
        super(FillDeviceConfigsRunner, self)._progress_update(progress)
        self.progress_changed.emit(progress)

class ReadConfigParametersRunner(config_util.GeneratorRunner):
    progress_changed = Signal(object)

    def __init__(self, devices, parent_widget, parent=None):
        super(ReadConfigParametersRunner, self).__init__(parent=parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.devices = devices
        self.parent_widget = parent_widget

    def _start(self):
        self.generator = config_util.read_config_parameters(self.devices)

    def _object_yielded(self, obj):
        if isinstance(obj, hardware_controller.TimeoutError):

            answer = QMB.question(
                    self.parent_widget,
                    "Connection error",
                    "Timeout connecting to %s" % obj.args[0],
                    buttons=QMB.Retry | QMB.Ignore | QMB.Abort,
                    defaultButton=QMB.Retry)

            return (std_button_to_cfg_action(answer), False)

        raise ValueError("Error: %s" % obj)

    def _progress_update(self, progress):
        super(ReadConfigParametersRunner, self)._progress_update(progress)
        self.progress_changed.emit(progress)
