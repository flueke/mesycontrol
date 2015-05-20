#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import argparse
import logging
import os
import signal
import sys

import pyqtgraph.console
pg = pyqtgraph

from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui
from mesycontrol import util

if __name__ == "__main__":
    if not sys.platform.startswith('win32'):
        parser = argparse.ArgumentParser(description='mesycontrol GUI command line arguments')
        parser.add_argument('--logging-config', metavar='FILE')
        opts = parser.parse_args()
    else:
        opts = None

    # Logging setup
    if opts is not None and opts.logging_config is not None:
        logging.config.fileConfig(opts.logging_config)
    else:
        logging.basicConfig(level=logging.DEBUG,
                format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

        logging.getLogger("PyQt4.uic").setLevel(logging.INFO)

    logging.info("Starting up...")

    # Signal handling
    signal.signum_to_name = dict((getattr(signal, n), n)
            for n in dir(signal) if n.startswith('SIG') and '_' not in n)

    def signal_handler(signum, frame):
        logging.info("Received signal %s. Quitting...",
                signal.signum_to_name.get(signum, "%d" % signum))
        QtGui.QApplication.quit()

    signal.signal(signal.SIGINT, signal_handler)

    # Create an exception hook registry and register the original handler with
    # it.
    sys.excepthook = util.ExceptionHookRegistry()
    sys.excepthook.register_handler(sys.__excepthook__)

    # Qt setup
    QtCore.QLocale.setDefault(QtCore.QLocale.c())
    QtGui.QApplication.setDesktopSettingsAware(False)
    app = QtGui.QApplication(sys.argv)
    app.setStyle(QtGui.QStyleFactory.create("Plastique"))

    # Let the interpreter run every 500 ms to be able to react to signals
    # arriving from the OS.
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    # Confine garbage collection to the main thread to avoid crashes.
    garbage_collector = util.GarbageCollector()

    # Update the environments path to easily find the mesycontrol_server binary.
    main_file = sys.executable if getattr(sys, 'frozen', False) else __file__
    bin_dir   = os.path.abspath(os.path.dirname(main_file))
    os.environ['PATH'] = bin_dir + os.pathsep + os.environ['PATH']

    logging.debug("PATH=%s", os.environ['PATH'])

    # Application setup
    from mesycontrol import app_model as am
    from mesycontrol import basic_model as bm
    from mesycontrol import config_model as cm
    from mesycontrol import mc_treeview

    hw_reg   = bm.MRCRegistry()
    cfg_reg  = cm.Setup()
    director = am.Director(hw_reg, cfg_reg)

    mc_tv = mc_treeview.MCTreeView(director)
    mc_tv.show()

    console = pg.console.ConsoleWidget(namespace=locals())
    console.show()

    #mainwin = MainWindow(context=context)
    #mainwin.show()
    ret = app.exec_()

    #del mainwin
    del garbage_collector

    sys.exit(ret)
