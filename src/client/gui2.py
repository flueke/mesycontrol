#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import argparse
import logging
import os
import signal
import sys

from mesycontrol import app_context
from mesycontrol import gui
from mesycontrol import util
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui

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
        logging.getLogger("mesycontrol.tcp_client.MCTCPClient").setLevel(logging.INFO)
        logging.getLogger("mesycontrol.basic_tree_model").setLevel(logging.INFO)
        logging.getLogger("mesycontrol.mc_treeview").setLevel(logging.INFO)

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
    app = QtGui.QApplication(sys.argv)
    app.setStyle(QtGui.QStyleFactory.create("Windows"))

    # Let the interpreter run every 500 ms to be able to react to signals
    # arriving from the OS.
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    # Confine garbage collection to the main thread to avoid crashes.
    garbage_collector = util.GarbageCollector()

    # Path setup
    main_file = sys.executable if getattr(sys, 'frozen', False) else __file__
    bin_dir   = os.path.abspath(os.path.dirname(main_file))
    data_dir  = util.find_data_dir(main_file)

    # Update the environments path to easily find the mesycontrol_server binary.
    os.environ['PATH'] = bin_dir + os.pathsep + os.environ['PATH']

    logging.debug("main_file=%s, bin_dir=%s, data_dir=%s", main_file, bin_dir, data_dir)

    # Application setup
    context = app_context.Context(main_file, bin_dir, data_dir, auto_load_modules=False)

    with app_context.use(context):
        mainwindow      = gui.MainWindow(context)
        gui_application = gui.GUIApplication(context, mainwindow)
        mainwindow.show()

        ret = app.exec_()

    del mainwindow
    del garbage_collector

    sys.exit(ret)
