#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
import contextlib
import os

import app_model as am
import basic_model as bm
import config_model as cm
import device_registry
import future
import util

class Context(QtCore.QObject):
    def __init__(self, main_file, bin_dir, data_dir, auto_load_modules=True, parent=None):
        super(Context, self).__init__(parent)
        self.log                = util.make_logging_source_adapter(__name__, self)
        self.main_file          = main_file
        self.bin_dir            = bin_dir
        self.data_dir           = data_dir
        self.device_registry    = device_registry.DeviceRegistry(auto_load_modules)

        hw_registry         = bm.MRCRegistry()  # Root of the hardware model tree
        setup               = cm.Setup()        # Root of the config model tree
        self.app_registry   = am.MRCRegistry(hw_registry, setup) # Root of the app model tree
        self.director       = am.Director(self.app_registry, self.device_registry)

    def init_device_registry(self):
        self.device_registry.load_system_deviceprofile_modules()
        self.device_registry.load_system_device_modules()

    def shutdown(self):
        observer = future.FutureObserver()

        def do_disconnect():
            futures = [mrc.disconnect() for mrc in self.app_registry.hw.get_mrcs()]
            observer.set_future(future.all_done(*futures))

        util.wait_for_signal(signal=observer.done, emitting_callable=do_disconnect, timeout_ms=5000)

    def find_data_file(self, filename):
        return os.path.join(self.data_dir, filename)

    def make_qsettings(self):
        return QtCore.QSettings("mesytec", "mesycontrol")

    def reset_setup(self):
        self.app_registry.setup = cm.Setup()

    setup = property(
            fget=lambda self: self.app_registry.get_config(),
            fset=lambda self, setup: self.app_registry.set_config(setup),
            doc="The contexts current setup object.")

@contextlib.contextmanager
def make(*args, **kwargs):
    """Creates and yields a Context object. Makes sure shutdown() is called on
    the context after use.
    Usage:
        with app_context.make(...) as context:
            do_things_with(context)
    """
    context = Context(*args, **kwargs)
    try:
        yield context
    finally:
        context.shutdown()

@contextlib.contextmanager
def use(context):
    """Same as make() but takes a Context instance instead of creating one."""
    try:
        yield context
    finally:
        context.shutdown()
