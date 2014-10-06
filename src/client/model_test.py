#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import logging
import signal
import sys

from PyQt4 import QtCore

from mesycontrol import application_model
from mesycontrol import mrc_connection
from mesycontrol import mrc_controller
from mesycontrol import hw_model

def signal_handler(signum, frame):
    logging.info("Received signal %s. Quitting...",
            signal.signum_to_name.get(signum, "%d" % signum))
    QtCore.QCoreApplication.quit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')
    logging.getLogger("PyQt4.uic").setLevel(logging.INFO)
    logging.getLogger("mesycontrol.tcp_client").setLevel(logging.INFO)

    signal.signum_to_name = dict((getattr(signal, n), n)
            for n in dir(signal) if n.startswith('SIG') and '_' not in n)
    signal.signal(signal.SIGINT, signal_handler)

    app = QtCore.QCoreApplication(sys.argv)

    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    application_model.instance = application_model.ApplicationModel(
            sys.executable if getattr(sys, 'frozen', False) else __file__)

    connection       = mrc_connection.factory(serial_port='/dev/ttyUSB0', baud_rate=115200)
    model            = hw_model.MRCModel()
    model.controller = mrc_controller.MRCController(connection, model)

    def on_qapp_quit():
        application_model.instance.shutdown()
        connection.disconnect()

    QtCore.QCoreApplication.instance().aboutToQuit.connect(on_qapp_quit)

    def on_device_added(device):
        print "device added:", str(device), device.controller

        def on_device_state_changed(old_state, new_state, info):
            if new_state == hw_model.DeviceModel.Ready:
                print "device %s is ready" % device

        device.state_changed.connect(on_device_state_changed)

    def on_mrc_model_state_changed(old_state, new_state, info):
        print "mrc_model state changed: old=%d, new=%d, info=%s" % (old_state, new_state, str(info))

    model.device_added.connect(on_device_added)
    model.state_changed.connect(on_mrc_model_state_changed)

    model.controller.connect()

    ret = app.exec_()

    del model

    sys.exit(ret)
