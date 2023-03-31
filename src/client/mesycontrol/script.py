#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import logging
import signal
import contextlib
import sys

from mesycontrol.qt import QtCore, Property
from mesycontrol import app_context, util, mrc_connection, hardware_controller, hardware_model, future

class DeviceWrapper(QtCore.QObject):
    def __init__(self, device, parent=None):
        super(DeviceWrapper, self).__init__(parent)
        self._wrapped = device

    def __getitem__(self, key):
        return ReadParameter(self._wrapped, key)()

    def __setitem__(self, key, value):
        return SetParameter(self._wrapped, key, value)()

    def __getattr__(self, attr):
        return getattr(self._wrapped, attr)

    def get_rc(self):
        return self._wrapped.rc

    def set_rc(self, rc):
        SetRc(self._wrapped, rc)()

    def __str__(self):
        return str(self._wrapped)

    rc = Property(bool, get_rc, set_rc)

class MRCWrapper(QtCore.QObject):
    def __init__(self, mrc, parent=None):
        super(MRCWrapper, self).__init__(parent)
        self._wrapped = mrc

    def __getitem__(self, bus):
        if bus not in range(2):
            raise KeyError("No such bus: %d" % bus)

        class bus_proxy(object):
            def __getitem__(proxy_self, dev):
                return DeviceWrapper(self._wrapped.get_device(bus, dev))

            def __str__(proxy_self):
                parts = list()
                for device in self._wrapped.get_devices(bus=bus):
                    parts.append("%d: %s" % (device.address, device))

                return "Bus %i: {%s}" % (bus, ", ".join(parts))

        return bus_proxy()

    def __getattr__(self, attr):
        return getattr(self._wrapped, attr)

    def connectMrc(self):
        fo = future.FutureObserver(self._wrapped.connectMrc())
        if not fo.done():
            util.wait_for_signal(signal=fo.done)
        return fo.result()

    def __str__(self):
        return str(self._wrapped)

class ScriptContext(object):
    def __init__(self, app_context):
        self.context = app_context

    def make_mrc(self, url):
        connection = mrc_connection.factory(url=url)
        controller = hardware_controller.Controller(connection)
        mrc = hardware_model.HardwareMrc(url)
        mrc.set_controller(controller)
        self.context.app_registry.add_mrc(mrc)
        return MRCWrapper(mrc)

@contextlib.contextmanager
def get_script_context():
    try:
        context = None

        # Setup logging. Has no effect if logging has already been setup
        logging.basicConfig(level=logging.NOTSET,
                format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')
        if logging.getLogger().level == logging.NOTSET:
            logging.getLogger().handlers[0].setLevel(logging.DEBUG)

        # If a QCoreApplication or QApplication instance exists assume
        # everything is setup and ready. Otherwise install the custom garbage
        # collector and setup signal handling.
        qapp = QtCore.QCoreApplication.instance()

        if qapp is None:
            qapp = QtCore.QCoreApplication(sys.argv)
            gc   = util.GarbageCollector()

            # Signal handling
            def signal_handler(signum, frame):
                logging.info("Received signal %s. Quitting...",
                        signal.signum_to_name.get(signum, "%d" % signum))
                qapp.quit()

            signal.signum_to_name = dict((getattr(signal, n), n)
                    for n in dir(signal) if n.startswith('SIG') and '_' not in n)
            signal.signal(signal.SIGINT, signal_handler)

            context = app_context.Context(
                    sys.executable if getattr(sys, 'frozen', False) else __file__)

        yield ScriptContext(context)
    except CommandInterrupted:
        pass
    finally:
        if context is not None:
            context.shutdown()
        try:
            del gc
        except NameError:
            pass
