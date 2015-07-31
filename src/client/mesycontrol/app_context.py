#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
import contextlib
import os

import app_model as am
import basic_model as bm
import config_model as cm
import config_xml
import device_registry
import future
import model_util
import util

class Context(QtCore.QObject):
    def __init__(self, main_file, auto_load_device_modules=True, parent=None):
        super(Context, self).__init__(parent)
        self.log                = util.make_logging_source_adapter(__name__, self)
        self.main_file          = main_file
        self.device_registry    = device_registry.DeviceRegistry(auto_load_device_modules)

        hw_registry         = bm.MRCRegistry()  # Root of the hardware model tree
        setup               = cm.Setup()        # Root of the config model tree
        self.app_registry   = am.MRCRegistry(hw_registry, setup) # Root of the app model tree
        self.director       = am.Director(self.app_registry, self.device_registry)

        self._shutdown_callbacks = list()

    def init_device_registry(self):
        self.device_registry.load_system_modules()

    def shutdown(self):
        observer = future.FutureObserver()

        def do_disconnect():
            futures = [mrc.disconnect() for mrc in self.app_registry.hw.get_mrcs()]
            observer.set_future(future.all_done(*futures))

        util.wait_for_signal(signal=observer.done, emitting_callable=do_disconnect, timeout_ms=5000)

        for cb in self._shutdown_callbacks:
            try:
                cb()
            except Exception:
                self.log.exception("shutdown callback %s raised", cb)

    def add_shutdown_callback(self, cb):
        self._shutdown_callbacks.append(cb)

    def make_qsettings(self):
        return QtCore.QSettings("mesytec", "mesycontrol")

    def open_setup(self, filename):
        setup = config_xml.read_setup(filename)

        for mrc in setup:
            for device in mrc:
                model_util.set_default_device_extensions(device, self.device_registry)

        setup.modified = False

        if not len(setup):
            raise RuntimeError("No MRC configurations found in %s" % filename)

        self.setup = setup
        self.set_setup_directory_hint(filename)
        return setup

    def reset_setup(self):
        self.app_registry.setup = cm.Setup()

    def get_setup_directory_hint(self):
        s = self.make_qsettings()

        v = s.value('Files/last_setup_file', QtCore.QString()).toString()
        v = os.path.dirname(str(v))

        if not len(v):
            v = str(s.value('Files/last_setup_directory', QtCore.QString()).toString())

        return v

    def set_setup_directory_hint(self, filename):
        s = self.make_qsettings()
        s.setValue('Files/last_setup_file', filename)
        s.setValue('Files/last_setup_directory', os.path.dirname(filename))

    def get_config_directory_hint(self):
        s = self.make_qsettings()

        v = s.value('Files/last_config_file', QtCore.QString()).toString()
        v = os.path.dirname(str(v))

        if not len(v):
            v = str(s.value('Files/last_config_dir', QtCore.QString()).toString())

        return v

    def set_config_directory_hint(self, filename):
        s = self.make_qsettings()
        s.setValue('Files/last_config_file', filename)
        s.setValue('Files/last_config_dir', os.path.dirname(filename))

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
