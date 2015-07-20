#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import argparse
import logging
import os
import signal
import sys
import weakref

from mesycontrol import app_context
from mesycontrol import gui
from mesycontrol import util
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui

if __name__ == "__main__":
    if not sys.platform.startswith('win32'):
        parser = argparse.ArgumentParser(description='mesycontrol GUI command line arguments')
        parser.add_argument('--logging-config', metavar='FILE')
        parser.add_argument('--setup', metavar='FILE')
        opts = parser.parse_args()
    else:
        opts = None

    # Logging setup
    if opts is not None and opts.logging_config is not None:
        logging.config.fileConfig(opts.logging_config)
    else:
        logging.basicConfig(level=logging.DEBUG,
                format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

        logging.getLogger().addHandler(logging.FileHandler("mesycontrol.log", "w"))
        logging.getLogger("mesycontrol.basic_tree_model").setLevel(logging.INFO)
        #logging.getLogger("mesycontrol.future").setLevel(logging.INFO)
        logging.getLogger("mesycontrol.mc_treeview").setLevel(logging.INFO)
        #logging.getLogger("mesycontrol.tcp_client.MCTCPClient").setLevel(logging.INFO)
        logging.getLogger("PyQt4.uic").setLevel(logging.INFO)

    logging.info("Starting up...")

    # Signal handling
    signal.signum_to_name = dict((getattr(signal, n), n)
            for n in dir(signal) if n.startswith('SIG') and '_' not in n)

    class SignalHandler(object):
        def __init__(self):
            self._called = False
            self._app = None

        def set_app(self, app):
            self._app = weakref.ref(app)

        def get_app(self):
            return self._app() if self._app is not None else None

        def __call__(self, signum, frame):

            if not self._called and self.get_app() is not None:
                logging.info("Received signal %s. Quitting...",
                        signal.signum_to_name.get(signum, "%d" % signum))

                self._called = True
                self.get_app().quit()
            else:
                logging.info("Received signal %s. Forcing quit...",
                        signal.signum_to_name.get(signum, "%d" % signum))

                QtGui.QApplication.quit()

    sigint_handler = SignalHandler()
    signal.signal(signal.SIGINT, sigint_handler)

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

    # Update the environments path to easily find the mesycontrol_server binary.
    os.environ['PATH'] = bin_dir + os.pathsep + os.environ['PATH']

    logging.debug("main_file=%s, bin_dir=%s", main_file, bin_dir)

    # Application setup
    context     = app_context.Context(main_file, auto_load_device_modules=False)
    setup_file  = None
    settings    = context.make_qsettings()

    if opts is not None and opts.setup is not None:
        setup_file = opts.setup
    elif settings.value('Options/open_last_setup_at_start', False).toBool():
        setup_file = str(settings.value('Files/last_setup_file', str()).toString())

    with app_context.use(context):
        mainwindow      = gui.MainWindow(context)
        gui_application = gui.GUIApplication(context, mainwindow)
        sigint_handler.set_app(gui_application)
        mainwindow.show()

        if setup_file:
            try:
                context.open_setup(setup_file)
            except Exception as e:
                settings.remove('Files/last_setup_file')
                QtGui.QMessageBox.critical(mainwindow, "Error",
                        "Opening setup file %s failed:\n%s" % (setup_file, e))

        ret = app.exec_()

    del mainwindow
    del garbage_collector

    sys.exit(ret)
