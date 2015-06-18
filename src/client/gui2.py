#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
import argparse
import logging
import os
import signal
import sys
import weakref

import pyqtgraph.console
pg = pyqtgraph

from mesycontrol.app_context import Context
from mesycontrol import basic_model as bm
from mesycontrol import config_model as cm
from mesycontrol import config_tree_model as ctm
from mesycontrol import config_xml
from mesycontrol import device_tableview
from mesycontrol import hardware_controller
from mesycontrol import hardware_model as hm
from mesycontrol import hardware_tree_model as htm
from mesycontrol import log_view
from mesycontrol import mrc_connection
from mesycontrol import util
from mesycontrol.mc_treeview import MCTreeView
from mesycontrol.qt import Qt
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui
from mesycontrol.qt import uic
from mesycontrol.ui.dialogs import AddDeviceDialog
from mesycontrol.ui.dialogs import AddMRCDialog

log = logging.getLogger('gui')

def add_mrc_connection(registry, url, do_connect):
    """Adds an MRC connection using the given url to the application registry.
    If `do_connect' is True this function will start a connection attempt and
    return the corresponding Future object. Otherwise the newly added MRC will
    be in disconnected state and None is returned."""

    connection      = mrc_connection.factory(url=url)
    controller      = hardware_controller.Controller(connection)
    mrc             = hm.MRC(url)
    mrc.controller  = controller

    registry.hw.add_mrc(mrc)

    if do_connect:
        return mrc.connect()

    return None

def run_add_mrc_config_dialog(find_data_file, registry, parent_widget=None):
    urls_in_use = [mrc.url for mrc in registry.cfg.get_mrcs()]
    serial_ports = util.list_serial_ports()
    dialog = AddMRCDialog(find_data_file=find_data_file, serial_ports=serial_ports,
            urls_in_use=urls_in_use, parent=parent_widget)
    dialog.setModal(True)

    def accepted():
        url, connect = dialog.result()
        mrc = cm.MRC(url)
        registry.cfg.add_mrc(mrc)

        if connect:
            mrc = registry.hw.get_mrc(url)
            if not mrc:
                add_mrc_connection(registry, url, True)
            elif mrc.is_disconnected():
                mrc.connect()

    dialog.accepted.connect(accepted)
    dialog.show()

def run_add_mrc_connection_dialog(find_data_file, registry, parent_widget=None):
    urls_in_use = [mrc.url for mrc in registry.hw.get_mrcs()]
    serial_ports = util.list_serial_ports()
    dialog = AddMRCDialog(find_data_file, serial_ports=serial_ports, urls_in_use=urls_in_use,
            do_connect_default=True, parent=parent_widget)
    dialog.setModal(True)

    def accepted():
        try:
            url, connect = dialog.result()
            add_mrc_connection(registry, url, connect)
        except Exception as e:
            log.exception("run_add_mrc_connection_dialog")
            QtGui.QMessageBox.critical(parent_widget, "Error", str(e))

    dialog.accepted.connect(accepted)
    dialog.show()

def run_add_device_config_dialog(device_registry, registry, mrc, bus=None, parent_widget=None):
    try:
        aa = [(b, d) for b in bm.BUS_RANGE for d in bm.DEV_RANGE
                if not mrc.cfg or not mrc.cfg.get_device(b, d)]
        dialog = AddDeviceDialog(bus=bus, available_addresses=aa, known_idcs=device_registry.get_device_names(), parent=parent_widget)
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
    except RuntimeError as e:
        log.exception(e)
        QtGui.QMessageBox.critical(parent_widget, "Error", str(e))

def run_open_setup_dialog(context, parent_widget):
    directory_hint = os.path.dirname(str(context.make_qsettings().value(
            'Files/last_setup_file', QtCore.QString()).toString()))

    filename = QtGui.QFileDialog.getOpenFileName(parent_widget, "Open setup file",
            directory=directory_hint, filter="XML files (*.xml);; *")

    if not len(filename):
        return

    try:
        setup = config_xml.read_setup(filename)
        
        if not len(setup):
            raise RuntimeError("No MRC configurations found in %s" % filename)

        context.app_registry.cfg = setup

    except Exception as e:
        log.exception(e)
        QtGui.QMessageBox.critical(parent_widget, "Error", "Opening setup %s failed: %s" % (filename, e))

class GUIApplication(object):
    def __init__(self, mainwindow):
        self.log = util.make_logging_source_adapter(__name__, self)
        self._mainwindow = weakref.ref(mainwindow)
        self.context  = mainwindow.context
        self.registry = self.context.app_registry

        self.treeview = self.mainwindow.treeview
        self.treeview.cfg_context_menu_requested.connect(self._cfg_context_menu)
        self.treeview.hw_context_menu_requested.connect(self._hw_context_menu)

        self.logview = self.mainwindow.logview

        self.registry.hw.mrc_added.connect(self._hw_mrc_added)

        self._device_table_windows = dict()

    def _hw_mrc_added(self, mrc):
        self.log.debug("hw mrc added: %s", mrc.url)
        mrc.connecting.connect(partial(self._hw_mrc_connecting, mrc=mrc))
        mrc.disconnected.connect(partial(self._hw_mrc_disconnected, mrc=mrc))

    def _hw_mrc_connecting(self, f, mrc):
        self.log.debug("_hw_mrc_connecting: f=%s, mrc=%s, mrc.url=%s", f, mrc, mrc.url)
        self.logview.append("Connecting to %s" % mrc.url)
        def done(f):
            try:
                f.result()
                self.logview.append("Connected to %s" % mrc.url)
                self.log.debug("Connected to %s", mrc.url)
            except Exception as e:
                self.logview.append("Error connecting to %s: %s" % (mrc.url, e))
                self.log.error("Error connecting to %s: %s", mrc.url, e)

        def progress(f):
            txt = f.progress_text()
            if txt:
                self.logview.append("%s: %s" % (mrc.url, txt))
                self.log.debug("Connection progress: %s: %s", mrc.url, txt)

        f.add_done_callback(done).add_progress_callback(progress)

    def _hw_mrc_disconnected(self, mrc):
        self.logview.append("Disconnected from %s" % mrc.url)

    #def _hw_mrc_connection_error(self, error, mrc):
    #    self.logview.append("%s: Connection error: %s" % (mrc.url, error))

    def get_mainwindow(self):
        return self._mainwindow()

    mainwindow = property(get_mainwindow)

    def _cfg_context_menu(self, node, idx, pos, view):
        menu = QtGui.QMenu()

        if isinstance(node, ctm.SetupNode):
            setup = node.ref.cfg

            menu.addAction("Open Setup").triggered.connect(partial(run_open_setup_dialog,
                context=self.context, parent_widget=self.treeview))

            #menu.addAction("Load Setup")

            if len(setup):
                if len(setup.filename):
                    menu.addAction("Save Setup")
                menu.addAction("Save Setup As")

            menu.addAction("Add MRC").triggered.connect(partial(run_add_mrc_config_dialog,
                find_data_file=self.context.find_data_file, registry=self.registry,
                parent_widget=self.treeview))

        if isinstance(node, ctm.MRCNode):
            menu.addAction("Add Device").triggered.connect(partial(run_add_device_config_dialog,
                device_registry=self.context.device_registry, registry=self.registry,
                mrc=node.ref, parent_widget=self.treeview))

            def remove_mrc():
                self.registry.cfg.remove_mrc(node.ref.cfg)

            #menu.addAction("Edit MRC").triggered.connect(partial(run_edit_mrc_config_dialog,
            #    context=self.context, registry=self.registry, mrc=node.ref, parent_widget=self.treeview))
            menu.addAction("Remove MRC").triggered.connect(remove_mrc)

        if isinstance(node, ctm.BusNode):
            menu.addAction("Add Device").triggered.connect(partial(run_add_device_config_dialog,
                device_registry=self.context.device_registry, registry=self.registry,
                mrc=node.parent.ref, bus=node.bus_number, 
                parent_widget=self.treeview))

        if isinstance(node, ctm.DeviceNode):
            def add_device_table_window():
                widget = device_tableview.DeviceTableWidget(device=node.ref, find_data_file=self.context.find_data_file)
                subwin = self.mainwindow.mdiArea.addSubWindow(widget)
                subwin.show()
                return subwin

            menu.addAction("Open").triggered.connect(add_device_table_window)
            menu.addAction("Load From File")
            menu.addAction("Save To File")
            menu.addAction("Remove Device from Config")

        if not menu.isEmpty():
            menu.exec_(view.mapToGlobal(pos))


    def _hw_context_menu(self, node, idx, pos, view):
        print "_hw_context_menu", node, idx, pos, view
        menu = QtGui.QMenu()

        if isinstance(node, htm.RegistryNode):
            menu.addAction("Add MRC Connection").triggered.connect(partial(run_add_mrc_connection_dialog,
                find_data_file=self.context.find_data_file, registry=self.registry, parent_widget=self.treeview))

        if isinstance(node, htm.MRCNode):
            mrc = node.ref

            if mrc.hw:
                print ("_hw_context_menu on MRCNode: connected=%s, connecting=%s, disconnected=%s" %
                        (mrc.hw.is_connected(), mrc.hw.is_connecting(), mrc.hw.is_disconnected()))

            if not mrc.hw or mrc.hw.is_disconnected():
                def do_connect():
                    if not mrc.hw:
                        add_mrc_connection(self.registry, mrc.url, True)
                    else:
                        mrc.hw.connect()

                menu.addAction("Connect").triggered.connect(do_connect)

            if mrc.hw and mrc.hw.is_connected():
                def do_scanbus():
                    for i in bm.BUS_RANGE:
                        mrc.hw.scanbus(i)
                menu.addAction("Scanbus").triggered.connect(do_scanbus)

            if mrc.hw and (mrc.hw.is_connected() or mrc.hw.is_connecting()):
                menu.addAction("Disconnect").triggered.connect(mrc.hw.disconnect)

            if mrc.hw:
                def do_disconnect():
                    mrc.hw.disconnect().add_done_callback(do_remove)

                def do_remove(f):
                    self.registry.hw.remove_mrc(mrc.hw)

                menu.addAction("Remove MRC Connection").triggered.connect(do_disconnect)

        if isinstance(node, htm.BusNode):
            mrc = node.parent.ref
            bus = node.bus_number

            if mrc.hw and mrc.hw.is_connected():
                menu.addAction("Scanbus").triggered.connect(partial(mrc.hw.scanbus, bus))

        if isinstance(node, htm.DeviceNode):
            def add_device_table_window():
                widget = device_tableview.DeviceTableWidget(device=node.ref, find_data_file=self.context.find_data_file)
                subwin = self.mainwindow.mdiArea.addSubWindow(widget)
                subwin.show()
                return subwin
            menu.addAction("Open").triggered.connect(add_device_table_window)

        if not menu.isEmpty():
            menu.exec_(view.mapToGlobal(pos))

class MainWindow(QtGui.QMainWindow):
    def __init__(self, context, parent=None):
        super(MainWindow, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.context = context

        QtCore.QCoreApplication.instance().aboutToQuit.connect(self._on_qapp_quit)
        uic.loadUi(context.find_data_file('mesycontrol/ui/mainwin.ui'), self)

        # Treeview
        self.treeview = MCTreeView(app_director=context.director,
                find_data_file=context.find_data_file,
                device_registry=context.device_registry)

        dw_tree = QtGui.QDockWidget("Device tree", self)
        dw_tree.setObjectName("dw_treeview")
        dw_tree.setWidget(self.treeview)
        dw_tree.setFeatures(QtGui.QDockWidget.DockWidgetMovable | QtGui.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dw_tree)

        # Log view
        self.logview = log_view.LogView(parent=self)
        dw_logview = QtGui.QDockWidget("Application Log", self)
        dw_logview.setObjectName("dw_logview")
        dw_logview.setWidget(self.logview)
        dw_logview.setFeatures(QtGui.QDockWidget.DockWidgetMovable | QtGui.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dw_logview)

        self.gui_app = GUIApplication(self)

    def _on_qapp_quit(self):
        logging.info("Exiting...")
        self.context.shutdown()

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
    context = Context(main_file, bin_dir, data_dir)
    mainwindow = MainWindow(context)
    mainwindow.show()

    ret = app.exec_()

    del mainwindow
    del garbage_collector

    sys.exit(ret)

