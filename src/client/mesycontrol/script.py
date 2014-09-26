#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import contextlib, logging, signal, sys
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty

from command import *
from mrc_command import *
import application_registry
import util

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

    rc = pyqtProperty(bool, get_rc, set_rc)

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

    def connect(self):
        return util.wait_for_signal(
                signal=self._wrapped.ready,
                expected_args=(True,),
                emitting_callable=self._wrapped.connect)

    def __str__(self):
        return str(self._wrapped)

class Context(object):
    def __init__(self):
        pass

    def make_connection(self, **kwargs):
        mrc = application_registry.instance.make_mrc_connection(**kwargs)
        return MRCWrapper(mrc)

@contextlib.contextmanager
def get_script_context():
    try:
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

            application_registry.instance = application_registry.ApplicationRegistry(
                    sys.executable if getattr(sys, 'frozen', False) else __file__)

        yield Context()
    except CommandInterrupted:
        pass
    finally:
        application_registry.instance.shutdown()
        try:
            del gc
        except NameError:
            pass
