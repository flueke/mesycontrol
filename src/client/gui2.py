#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
import argparse
import logging
import os
import signal
import sys

import pyqtgraph.console
pg = pyqtgraph

from mesycontrol import basic_model as bm
from mesycontrol import config_model as cm
from mesycontrol import config_tree_model as ctm
from mesycontrol import hardware_model as hm
from mesycontrol import util
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui
from mesycontrol.ui.dialogs import AddDeviceDialog
from mesycontrol.ui.dialogs import AddMRCDialog

class MainWindow(QtGui.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)

def run_add_mrc_config(registry, parent_widget=None):
    urls_in_use = [mrc.url for mrc in registry.cfg.get_mrcs()]
    dialog = AddMRCDialog(urls_in_use=urls_in_use, parent=parent_widget)
    dialog.setModal(True)

    def accepted():
        url, name, connect = dialog.result()
        mrc = cm.MRC(url)
        mrc.name = name
        registry.cfg.add_mrc(mrc)

        if connect:
            mrc = registry.hw.get_mrc(url)
            if not mrc:
                mrc = hm.MRC(url)
                mrc.connection = mrc_connection.factory(url=url)
                mrc.controller = hardware_controller.Controller()
                registry.hw.add_mrc(mrc)
            if mrc.is_disconnected():
                mrc.connect() # TODO: watch this and display progress / success / error

    dialog.accepted.connect(accepted)
    dialog.show()

# TODO: known IDCs
def run_add_device_config(registry, mrc, bus=None, parent_widget=None):
    aa = [(b, d) for b in bm.BUS_RANGE for d in bm.DEV_RANGE
            if not mrc.cfg or not mrc.cfg.get_device(b, d)]
    dialog = AddDeviceDialog(bus=bus, available_addresses=aa, known_idcs=list(), parent=parent_widget)
    dialog.setModal(True)

    def accepted():
        bus, address, idc, name = dialog.result()
        device = cm.Device(bus, address, idc)
        device.name = name
        if not mrc.cfg:
            registry.cfg.add_mrc(cm.MRC(mrc.url))
        mrc.cfg.add_device(device)

    dialog.accepted.connect(accepted)
    dialog.show()

class Application(object):
    def __init__(self, mc_treeview):
        self.tv = mc_treeview
        self.tv.cfg_context_menu_requested.connect(self._cfg_context_menu)
        self.tv.hw_context_menu_requested.connect(self._hw_context_menu)
        self.tv.node_selected.connect(self._node_selected)
        self.director = self.tv.app_director
        self.registry = self.director.registry

    def _cfg_context_menu(self, node, idx, pos, view):
        menu = QtGui.QMenu()

        if isinstance(node, ctm.SetupNode):
            menu.addAction("Add MRC").triggered.connect(partial(run_add_mrc_config,
                registry=self.registry, parent_widget=self.tv))

        if isinstance(node, ctm.MRCNode):
            menu.addAction("Add Device").triggered.connect(partial(run_add_device_config,
                registry=self.registry, mrc=node.ref, parent_widget=self.tv))

        if isinstance(node, ctm.BusNode):
            menu.addAction("Add Device").triggered.connect(partial(run_add_device_config,
                bus=node.bus_number, registry=self.registry, mrc=node.parent.ref,
                parent_widget=self.tv))

        if not menu.isEmpty():
            menu.exec_(view.mapToGlobal(pos))

    def _hw_context_menu(self, node, idx, pos, view):
        print "_hw_context_menu", node, idx, pos, view

    def _node_selected(self, node, idx, view):
        print "_node_selected", node, idx, view

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
    #QtGui.QApplication.setDesktopSettingsAware(False)
    app = QtGui.QApplication(sys.argv)
    #app.setStyle(QtGui.QStyleFactory.create("Plastique"))

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
    from mesycontrol import mc_treeview

    hw_reg   = bm.MRCRegistry()
    cfg_reg  = cm.Setup()
    director = am.Director(hw_reg, cfg_reg)

    mc_tv = mc_treeview.MCTreeView(director)
    mc_tv.show()

    console = pg.console.ConsoleWidget(namespace=locals())
    console.show()

    from mesycontrol import mrc_connection
    from mesycontrol import hardware_model
    from mesycontrol import hardware_controller

    url = "serial:///dev/ttyUSB1"
    mrc = hardware_model.MRC(url)
    mrc.connection = mrc_connection.factory(url=url)
    mrc.controller = hardware_controller.Controller()
    hw_reg.add_mrc(mrc)
    #mrc.connect()

    mc_app = Application(mc_tv)

    ret = app.exec_()

    #del mainwin
    del garbage_collector

    sys.exit(ret)

