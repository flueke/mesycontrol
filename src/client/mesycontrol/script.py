#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import contextlib, logging, os, signal, sys
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from . import util
from . import application_model
from . import mrc_connection
from .command import CommandInterrupted
from .mrc_command import Connect, ReadParameter, SetParameter, SetRc, Scanbus

class DeviceWrapper(QtCore.QObject):
    def __init__(self, device_model, parent=None):
        super(DeviceWrapper, self).__init__(parent)
        self._wrapped = device_model

    def __getitem__(self, key):
        return ReadParameter(self._wrapped, key).exec_().get_result()

    def __setitem__(self, key, value):
        return SetParameter(self._wrapped, key, value).exec_().get_result()

    def __getattr__(self, attr):
        return getattr(self._wrapped, attr)

    def get_rc(self):
        return self._wrapped.rc

    def set_rc(self, rc):
        SetRc(self._wrapped, rc).exec_().get_result()

    rc = pyqtProperty(bool, get_rc, set_rc)

class MRCWrapper(QtCore.QObject):
    def __init__(self, mrc_model, parent=None):
        super(MRCWrapper, self).__init__(parent)
        self._wrapped = mrc_model

    def __getitem__(self, bus):
        if bus not in self._wrapped.device_models:
            raise KeyError("No such bus: %d" % bus)

        class bus_proxy(object):
            def __getitem__(proxy_self, dev):
                if dev not in self._wrapped.device_models[bus]:
                    raise KeyError("No such device: %d" % dev)
                return DeviceWrapper(self._wrapped.device_models[bus][dev])

            def __str__(proxy_self):
                parts = list()
                for addr, device in self._wrapped.device_models[bus].iteritems():
                    parts.append("%d: %s" % (addr, device))

                return "Bus %i: {%s}" % (bus, ", ".join(parts))

        return bus_proxy()

    def __getattr__(self, attr):
        return getattr(self._wrapped, attr)

class ConnectionWrapper(QtCore.QObject):
    def __init__(self, connection, parent=None):
        super(ConnectionWrapper, self).__init__(parent)
        self._wrapped = connection

    def connect(self):
        if not Connect(self._wrapped).exec_().get_result():
            return False

        for i in range(2):
            Scanbus(self._wrapped.mrc_model, i).exec_().get_result()

        return True

    def disconnect(self):
        self._wrapped.disconnect()

    def get_mrc(self):
        return MRCWrapper(self._wrapped.mrc_model)

    mrc = pyqtProperty(object, get_mrc)

class Context(object):
    def __init__(self):
        self.app_model = application_model.instance

    def make_connection(self, **kwargs):
        conn = mrc_connection.factory(**kwargs)
        application_model.instance.registerConnection(conn)
        return ConnectionWrapper(conn)

@contextlib.contextmanager
def get_script_context():
    try:
        logging.basicConfig(level=logging.INFO,
                format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

        qapp = QtCore.QCoreApplication(sys.argv)
        gc   = util.GarbageCollector(debug=False)

        # Signal handling
        def signal_handler(signum, frame):
            logging.info("Received signal %s. Quitting...",
                    signal.signum_to_name.get(signum, "%d" % signum))
            qapp.quit()

        signal.signum_to_name = dict((getattr(signal, n), n)
                for n in dir(signal) if n.startswith('SIG') and '_' not in n)
        signal.signal(signal.SIGINT, signal_handler)

        application_model.instance.bin_dir = os.path.abspath(os.path.dirname(
            sys.executable if getattr(sys, 'frozen', False) else __file__))

        yield Context()
    except CommandInterrupted:
        pass
    finally:
        print "Shutdown begin"
        application_model.instance.shutdown()
        print "Shutdown end"
        del gc
