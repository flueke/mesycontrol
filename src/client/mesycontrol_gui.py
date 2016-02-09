#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2016 mesytec GmbH & Co. KG <info@mesytec.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
__author__ = 'Florian Lüke'
__email__  = 'florianlueke@gmx.net'

__author__ = 'Florian Lüke'
__email__  = 'florianlueke@gmx.net'

import argparse
import logging
import os
import signal
import sys
import weakref

is_windows = sys.platform.startswith('win32')

try:
    import colorlog
except ImportError:
    colorlog = None

if colorlog and is_windows:
    try:
        import colorama
    except ImportError:
        colorama = None

from mesycontrol import app_context
from mesycontrol import gui
from mesycontrol import gui_mainwindow
from mesycontrol import util
from mesycontrol.qt import Qt
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui

if __name__ == "__main__":
    if not is_windows:
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
                format='[%(asctime)-15s] [%(name)s.%(levelname)-8s] %(message)s')

        if colorlog and (not is_windows or colorama):
            fmt  = '%(bg_blue)s[%(asctime)-15s]%(reset)s '
            fmt += '[%(green)s%(name)s%(reset)s.%(log_color)s%(levelname)-8s%(reset)s] %(message)s'
            fmt  = colorlog.ColoredFormatter(fmt)
            hdlr = logging.getLogger().handlers[0]
            hdlr.setFormatter(fmt)

        for ln in (
                "basic_tree_model",
                "future",
                "mc_treeview",
                "tcp_client.MCTCPClient",
                "hardware_controller.Controller",
                "PyQt4.uic"):
            logging.getLogger(ln).setLevel(logging.INFO)

        fn = QtGui.QDesktopServices.storageLocation(QtGui.QDesktopServices.DocumentsLocation)
        fn = os.path.join(str(fn), "mesycontrol.log")

        try:
            fh = logging.FileHandler(fn, "w")
            fh.setFormatter(logging.Formatter(fmt='[%(asctime)-15s] [%(name)s.%(levelname)-8s] %(message)s'))
            logging.getLogger().addHandler(fh)
        except IOError:
            pass

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
    app.setAttribute(Qt.AA_DontShowIconsInMenus, False)

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
    elif settings.value('Options/open_last_setup_at_start', True).toBool():
        setup_file = str(settings.value('Files/last_setup_file', str()).toString())

    with app_context.use(context):
        mainwindow      = gui_mainwindow.MainWindow(context)
        gui_application = gui.GUIApplication(context, mainwindow)
        sigint_handler.set_app(gui_application)
        mainwindow.show()
        mainwindow.restore_settings()

        if setup_file:
            try:
                context.open_setup(setup_file)
            except Exception as e:
                settings.remove('Files/last_setup_file')
                QtGui.QMessageBox.critical(mainwindow, "Error",
                        "Opening setup file %s failed:\n%s" % (setup_file, e))

        ret = app.exec_()
        logging.debug("app.exec_() returned %d", ret)

    del mainwindow
    del garbage_collector

    sys.exit(ret)
