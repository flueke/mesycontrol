#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import logging
import os
import signal
import sys

from mesycontrol import qt
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui

from mesycontrol import app_context
from mesycontrol import mscf16
from mesycontrol import hw_model
from mesycontrol import app_model
from mesycontrol import mrc_controller
from mesycontrol import config

def signal_handler(signum, frame):
    logging.info("Received signal %s. Quitting...",
            signal.signum_to_name.get(signum, "%d" % signum))
    QtGui.QApplication.quit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    signal.signum_to_name = dict((getattr(signal, n), n)
            for n in dir(signal) if n.startswith('SIG') and '_' not in n)
    signal.signal(signal.SIGINT, signal_handler)

    app     = qt.QtGui.QApplication(sys.argv)
    context = app_context.Context(sys.executable if getattr(sys, 'frozen', False) else __file__)
    # Update the environments path to easily find the mesycontrol_server binary.
    os.environ['PATH'] = context.bin_dir + os.pathsep + os.environ['PATH']

    try:
        bus_data    = [(0, 0) for i in range(16)]
        bus_data[0] = (mscf16.MSCF16.idcs[0], 1)
        mrc_model   = hw_model.MRCModel()
        mrc_model.controller = mrc_controller.VirtualMRCController(mrc_model)

        mrc_config  = config.MRCConfig()
        mrc         = app_model.MRC(mrc_model=mrc_model, mrc_config=mrc_config, context=context)

        mrc_model.set_scanbus_data(0, bus_data)

        device = mrc.get_device(0, 0)

        print device, type(device), device.get_memory()

        w = mscf16.MSCF16Widget(device, context)
        w.show()

        def print_device_mem():
            print device.get_memory()

        timer = QtCore.QTimer()
        timer.timeout.connect(print_device_mem)
        timer.start(500)

        app.exec_()

    finally:
        print("Bye, bye!")
        context.shutdown()
