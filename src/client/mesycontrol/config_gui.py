#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtGui

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

class ApplySetupRunner(config_util.GeneratorRunner):
    def __init__(self, source, dest, device_registry, parent_widget, parent=None):
        super(config_util.GeneratorRunner, self).__init__(parent=parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.source = source
        self.dest   = dest
        self.device_registry = device_registry
        self.parent_widget = parent_widget

    def _start(self):
        self.generator = config_util.connect_and_apply_setup(self.source, self.dest, self.device_registry)

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

        raise ValueError("unhandled object: %s" % obj)

class ApplyDeviceConfigRunner(config_util.GeneratorRunner):
    def __init__(self, source, dest, device_profile, parent=None):
        super(ApplyDeviceConfigRunner, self).__init__(parent=parent)

        self.log = util.make_logging_source_adapter(__name__, self)
        self.source = source
        self.dest   = dest
        self.device_profile = device_profile

    def _start(self):
        self.generator = config_util.apply_device_config(self.source, self.dest,
                self.device_profile)

