#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtGui
from qt import pyqtSignal

import config_util
import hardware_controller
import util

QMB = QtGui.QMessageBox

def std_button_to_cfg_action(button):
    if button == QMB.Retry:
        return config_util.ACTION_RETRY

    if button == QMB.Ignore:
        return config_util.ACTION_SKIP

    if button == QMB.Abort:
        return config_util.ACTION_ABORT

    raise ValueError("unknown button")

class SubProgressDialog(QtGui.QDialog):
    canceled = pyqtSignal()

    def __init__(self, parent=None):
        super(SubProgressDialog, self).__init__(parent)
        util.loadUi(":/ui/subprogress_widget.ui", self)
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
    progress_changed = pyqtSignal(object)

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

        raise ValueError("unhandled object: %s" % obj)

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