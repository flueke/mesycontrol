#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

# - UIs for known devices (MHV4, MSCF16)
# - Device descriptions used to read and write config files

import logging
import signal
import sys
from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSlot
from PyQt4.Qt import Qt
from mesycontrol import application_registry
from mesycontrol import app_model
from mesycontrol import device_widget
from mesycontrol import config
from mesycontrol import config_xml
from mesycontrol import hw_model
from mesycontrol import log_view
from mesycontrol import mrc_connection
from mesycontrol import mrc_controller
from mesycontrol import mrc_command
from mesycontrol import setup_treeview
from mesycontrol import util
from mesycontrol.ui.connect_dialog import ConnectDialog

class MainWindow(QtGui.QMainWindow):
    def __init__(self, parent = None):
        super(MainWindow, self).__init__(parent)
        QtCore.QCoreApplication.instance().aboutToQuit.connect(self.on_qapp_quit)
        uic.loadUi(application_registry.instance.find_data_file('mesycontrol/ui/mainwin.ui'), self)

        self._device_windows = {}

        self.setup_tree_view = setup_treeview.SetupTreeView(parent=self)
        self.setup_tree_view.sig_open_device.connect(self._slt_open_device_window)
        self.setup_tree_view.sig_remove_mrc.connect(self._slt_remove_mrc_from_setup)
        application_registry.instance.mrc_added.connect(self.setup_tree_view.model().add_mrc)
        application_registry.instance.mrc_removed.connect(self.setup_tree_view.model().remove_mrc)

        dw_setup_tree = QtGui.QDockWidget("Setup", self)
        dw_setup_tree.setWidget(self.setup_tree_view)
        dw_setup_tree.setFeatures(QtGui.QDockWidget.DockWidgetMovable | QtGui.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.LeftDockWidgetArea, dw_setup_tree)

        log_emitter = util.QtLogEmitter(parent=self)
        logging.getLogger().addHandler(log_emitter.get_handler())

        self.log_view = log_view.LogView(parent=self)
        log_emitter.log_record.connect(self.log_view.handle_log_record)
        application_registry.instance.register('exception_logger', self.log_view.handle_exception)

        dw_log_view = QtGui.QDockWidget("Application Log", self)
        dw_log_view.setWidget(self.log_view)
        dw_log_view.setFeatures(QtGui.QDockWidget.DockWidgetMovable | QtGui.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dw_log_view)

    def on_qapp_quit(self):
        logging.info("Exiting...")
        application_registry.instance.shutdown()

    @pyqtSlot()
    def on_actionConnect_triggered(self):
        dialog = ConnectDialog(self)
        result = dialog.exec_()

        if result != QtGui.QDialog.Accepted:
            return

        connection_config = dialog.connection_config
        connection        = application_registry.instance.find_connection_by_config(connection_config)

        if connection is not None:
            QtGui.QMessageBox.critical(self, "Connection error", "Connection exists")
            return

        application_registry.instance.make_mrc_connection(config=connection_config, connect=True)

    def _add_subwindow(self, widget, title):
        subwin = self.mdiArea.addSubWindow(widget)
        subwin.setWindowTitle(title)
        subwin.setAttribute(Qt.WA_DeleteOnClose, False)
        subwin.show()
        return subwin

    def _slt_open_device_window(self, device):
        if not self._device_windows.has_key(device):
            widget = device_widget.factory(device)
            widget.setParent(self)
            self._device_windows[device] = self._add_subwindow(widget, str(device))
            if not device.has_all_parameters():
                mrc_command.FetchMissingParameters(device).start()

        subwin = self._device_windows[device]
        subwin.show()
        subwin.widget().show()
        self.mdiArea.setActiveSubWindow(subwin)

    def _slt_remove_mrc_from_setup(self, mrc):
        mrc.disconnect()

        active_setup = application_registry.instance.get('active_setup')
        active_setup.remove_mrc_config(mrc.config)

        for device in mrc.get_devices():
            if device in self._device_windows:
                self.mdiArea.removeSubWindow(self._device_windows[device])
                del self._device_windows[device]

        application_registry.instance.unregister_mrc(mrc)

    @pyqtSlot()
    def on_actionLoad_Setup_triggered(self):
        filename = QtGui.QFileDialog.getOpenFileName(self, "Open setup file",
                filter="XML files (*.xml);; *")

        if not len(filename):
            return

        try:
            setup = config_xml.parse_file(filename)
        except config_xml.InvalidArgument as e:
            QtGui.QMessageBox.critical(self, "Error", "Opening setup %s failed: %s" % (filename, e))
            return

        if not len(setup.mrc_configs):
            QtGui.QMessageBox.critical(self, "Error", "No MRC configurations found in %s" % filename)
            return

        setup_loader = config.SetupLoader(setup)
        pd = QtGui.QProgressDialog(self)
        pd.setMaximum(0)
        pd.setValue(0)

        setup_loader.progress_changed.connect(pd.setValue)
        setup_loader.stopped.connect(pd.accept)
        QtCore.QTimer.singleShot(0, setup_loader.start)
        pd.exec_()

        if pd.wasCanceled():
            setup_loader.stop()

        if setup_loader.has_failed():
            QtGui.QMessageBox.critical(self, "Error", "Setup loading failed")

    @pyqtSlot()
    def on_actionSave_Setup_triggered(self):
        filename = QtGui.QFileDialog.getSaveFileName(self, "Save setup as",
                filter="XML files (*.xml);; *")

        if not len(filename):
            return

        setup = application_registry.instance.get('active_setup')

        if setup is None:
            return

        # Make sure the device config instances within the setup are complete
        # (all required parameters present).
        setup_completer = config.SetupCompleter(setup)
        pd = QtGui.QProgressDialog(self)
        pd.setMaximum(len(setup_completer))
        pd.setValue(0)

        setup_completer.progress_changed.connect(pd.setValue)
        setup_completer.stopped.connect(pd.accept)
        QtCore.QTimer.singleShot(0, setup_completer.start)
        pd.exec_()

        if pd.wasCanceled():
            setup_completer.stop()

        if setup_completer.has_failed():
            QtGui.QMessageBox.critical(self, "Error", "Setup building failed")
        else:
            try:
                with open(filename, 'w') as f:
                    config_xml.write_setup_to_file(setup, f)
            except IOError as e:
                QtGui.QMessageBox.critical(self, "Error", "Writing to %s failed: %s" % (filename, e))
            else:
                QtGui.QMessageBox.information(self, "Info", "Configuration written to %s" % filename)

def signal_handler(signum, frame):
    logging.info("Received signal %s. Quitting...",
            signal.signum_to_name.get(signum, "%d" % signum))
    QtGui.QApplication.quit()

def app_except_hook(exc_type, exc_value, exc_trace):
    if application_registry.instance is not None:
        exc_logger = application_registry.instance.get('exception_logger')
        if exc_logger is not None:
            exc_logger(exc_type, exc_value, exc_trace)

    sys.__excepthook__(exc_type, exc_value, exc_trace)

if __name__ == "__main__":
    # Logging setup
    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    #logging.getLogger("mesycontrol.tcp_client").setLevel(logging.DEBUG)
    logging.getLogger("PyQt4.uic").setLevel(logging.INFO)

    # Signal handling
    signal.signum_to_name = dict((getattr(signal, n), n)
            for n in dir(signal) if n.startswith('SIG') and '_' not in n)
    signal.signal(signal.SIGINT, signal_handler)

    application_registry.instance = application_registry.ApplicationRegistry(
            sys.executable if getattr(sys, 'frozen', False) else __file__)

    sys.excepthook = app_except_hook

    app = QtGui.QApplication(sys.argv)

    # Let the interpreter run every 500 ms to be able to react to signals
    # arriving from the OS.
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    # Confine garbage collection to the main thread to avoid crashes.
    garbage_collector = util.GarbageCollector()

    mainwin = MainWindow()
    mainwin.show()
    ret = app.exec_()

    del mainwin
    del garbage_collector

    sys.exit(ret)
