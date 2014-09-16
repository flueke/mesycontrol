#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import contextlib, logging, signal, sys
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty

from command import *
from mrc_command import *
import application_registry
import app_model
import hw_model
import mrc_connection
import mrc_controller
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
        if not Connect(self._wrapped)():
            return False

        # FIXME: Wait for the model to scan both busses (which it does once
        # it's connected)
        for i in range(2):
            Scanbus(self._wrapped, i)()

        return True

    def __str__(self):
        return str(self._wrapped)

#class ConnectionWrapper(QtCore.QObject):
#    def __init__(self, connection, parent=None):
#        super(ConnectionWrapper, self).__init__(parent)
#        self._wrapped = connection
#
#    def connect(self):
#        if not Connect(self._wrapped)():
#            return False
#
#        for i in range(2):
#            Scanbus(self._wrapped.mrc_model, i)()
#
#        return True
#
#    def disconnect(self):
#        self._wrapped.disconnect()
#
#    def get_mrc(self):
#        return MRCWrapper(self._wrapped.mrc_model)
#
#    def __getattr__(self, attr):
#        return getattr(self._wrapped, attr)
#
#    mrc = pyqtProperty(object, get_mrc)

class Context(object):
    def __init__(self):
        self.app_model = application_registry.instance

    def make_connection(self, **kwargs):
        #conn = mrc_connection.factory(**kwargs)
        #application_registry.instance.registerConnection(conn)
        #return ConnectionWrapper(conn)

        connection       = mrc_connection.factory(**kwargs)
        model            = hw_model.MRCModel()
        model.controller = mrc_controller.MesycontrolMRCController(connection, model)
        application_registry.instance.register_mrc_model(model)
        mrc = app_model.MRC(mrc_model=model)
        application_registry.instance.register_mrc(mrc)
        connection.connect()
        return MRCWrapper(mrc)

@contextlib.contextmanager
def get_script_context():
    try:
        # Setup logging. Has no effect if logging has already been setup
        logging.basicConfig(level=logging.NOTSET,
                format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')
        if logging.getLogger().level == logging.NOTSET:
            logging.getLogger().handlers[0].setLevel(logging.WARNING)

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
