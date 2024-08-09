#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import logging
import signal
import contextlib
import sys

from mesycontrol.qt import QtCore, Property
from mesycontrol import app_context, util, mrc_connection, hardware_controller, hardware_model
from mesycontrol.future import get_future_result

class DeviceWrapper(QtCore.QObject):
    def __init__(self, device, parent=None):
        super(DeviceWrapper, self).__init__(parent)
        self._wrapped = device

    def __getitem__(self, key):
        return self.read_parameter(key)

    def __setitem__(self, key, value):
        return self.set_parameter(key, value)

    def __getattr__(self, attr):
        return getattr(self._wrapped, attr)

    def __str__(self):
        return str(self._wrapped)

    def get_rc(self):
        return self._wrapped.rc

    def set_rc(self, onOff):
        return get_future_result(self._wrapped.set_rc(onOff))

    rc = Property(bool, get_rc, set_rc)

    def read_parameter(self, addr):
        return get_future_result(self._wrapped.read_parameter(addr))

    def set_parameter(self, addr, value):
        return get_future_result(self._wrapped.set_parameter(addr, value))


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

    def __str__(self):
        return str(self._wrapped)

    def connectMrc(self):
        return get_future_result(self._wrapped.connectMrc())

    def scanbus(self, bus):
        # Response is a protobuf ScanbusResult. Each object in the 'entries'
        # member is a ScanbusEntry object.
        response = get_future_result(self._wrapped.scanbus(bus)).response
        return response.scanbus_result.entries

    def get_devices(self, bus=None):
        devices = self._wrapped.get_devices(bus)
        return [DeviceWrapper(dev) for dev in devices]

class ScriptContext(object):
    def __init__(self, appContext):
        self.appContext: app_context.Context = appContext
        self.quit = False

    def make_mrc(self, url):
        connection = mrc_connection.factory(url=url)
        controller = hardware_controller.Controller(connection)
        mrc = hardware_model.HardwareMrc(url)
        mrc.set_controller(controller)
        self.appContext.app_registry.hw.add_mrc(mrc)
        return MRCWrapper(mrc)

    def get_device_profile(self, device_idc):
        return self.appContext.device_registry.get_device_profile(device_idc)

    def get_all_mrcs(self):
        return [mrc for mrc in self.appContext.app_registry.get_mrcs()]

    def shutdown(self):
        self.appContext.shutdown()

@contextlib.contextmanager
def get_script_context(log_level=logging.INFO):
    try:
        # Setup logging. Has no effect if logging has already been setup.
        logging.basicConfig(level=log_level,
                format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')
        if logging.getLogger().level == logging.NOTSET:
            logging.getLogger().handlers[0].setLevel(log_level)

        # If a QCoreApplication or QApplication instance exists assume
        # everything is setup and ready. Otherwise install the custom garbage
        # collector and setup signal handling.
        qapp = QtCore.QCoreApplication.instance()

        if qapp is None:
            qapp = QtCore.QCoreApplication(sys.argv)
            gc   = util.GarbageCollector()

            ## Signal handling
            #def signal_handler(signum, frame):
            #    logging.info("Received signal %s. Quitting...",
            #            signal.signum_to_name.get(signum, "%d" % signum))
            #    qapp.quit()

            #signal.signum_to_name = dict((getattr(signal, n), n)
            #        for n in dir(signal) if n.startswith('SIG') and '_' not in n)
            #signal.signal(signal.SIGINT, signal_handler)

        appContext = app_context.Context(
                sys.executable if getattr(sys, 'frozen', False) else __file__)
        scriptContext = ScriptContext(appContext)
        yield scriptContext
    finally:
        if scriptContext is not None:
            scriptContext.shutdown()
        try:
            del gc
        except NameError:
            pass
