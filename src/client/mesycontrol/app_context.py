#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
import os

import app_model as am
import basic_model as bm
import config_model as cm
import device_registry
import future
import util

class Context(QtCore.QObject):
    def __init__(self, main_file, bin_dir, data_dir, parent=None):
        super(Context, self).__init__(parent)
        self.log                    = util.make_logging_source_adapter(__name__, self)
        self.main_file              = main_file
        self.bin_dir                = bin_dir
        self.data_dir               = data_dir
        self.device_registry        = device_registry.DeviceRegistry()

        self.device_registry.load_system_deviceprofile_modules()
        self.device_registry.load_system_device_modules()

        self.hw_registry    = bm.MRCRegistry()  # Root of the hardware model tree
        self.setup          = cm.Setup()        # Root of the config model tree
        self.director       = am.Director(self.hw_registry, self.setup)
        self.app_registry   = self.director.registry

    def shutdown(self):
        observer = future.FutureObserver()

        def do_disconnect():
            futures = [mrc.disconnect() for mrc in self.hw_registry.get_mrcs()]
            observer.set_future(future.all_done(*futures))

        util.wait_for_signal(signal=observer.done, emitting_callable=do_disconnect, timeout_ms=5000)

    def find_data_file(self, filename):
        return os.path.join(self.data_dir, filename)

    def make_qsettings(self):
        return QtCore.QSettings("mesytec", "mesycontrol")
