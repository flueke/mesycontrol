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
from mesycontrol import mrc_connection
from mesycontrol import mrc_controller
from mesycontrol import mrc_command
from mesycontrol import setup_treeview
from mesycontrol import util
from mesycontrol.config import SetupBuilder, SetupLoader

class ConnectDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        super(ConnectDialog, self).__init__(parent)

        #uic.loadUi(resource_stream('mesycontrol.ui', 'connect_dialog.ui'), self)
        uic.loadUi(application_registry.instance.find_data_file('mesycontrol/ui/connect_dialog.ui'), self)
        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(False)
        self.combo_serial_port.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+')))
        self.le_tcp_host.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+')))
        self.le_mesycontrol_host.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+')))
        self.le_tcp_host.setText('localhost')
        self.le_mesycontrol_host.setText('localhost')

        for port in util.list_serial_ports():
            self.combo_serial_port.addItem(port)

        for le in self.findChildren(QtGui.QLineEdit):
            le.textChanged.connect(self._validate_inputs)

        for combo in self.findChildren(QtGui.QComboBox):
            combo.currentIndexChanged.connect(self._validate_inputs)
            combo.editTextChanged.connect(self._validate_inputs)

        self.stacked_widget.currentChanged.connect(self._validate_inputs)
        self._validate_inputs()

    @pyqtSlot()
    def _validate_inputs(self):
        page_widget = self.stacked_widget.currentWidget()
        is_ok       = True

        for le in page_widget.findChildren(QtGui.QLineEdit):
            is_ok = is_ok and le.hasAcceptableInput()

        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(is_ok)

    @pyqtSlot()
    def accept(self):
        self.connection_config      = config.MRCConnectionConfig()

        idx = self.stacked_widget.currentIndex()
        if idx == 0:
            self.connection_config.serial_device    = self.combo_serial_port.currentText()
            baud_text = self.combo_baud_rate.currentText()
            baud_rate = int(baud_text) if baud_text != 'auto' else 0
            self.connection_config.serial_baud_rate = baud_rate
        elif idx == 1:
            self.connection_config.tcp_host = self.le_tcp_host.text()
            self.connection_config.tcp_port = self.spin_tcp_port.value()
        elif idx == 2:
            self.connection_config.mesycontrol_host = self.le_mesycontrol_host.text()
            self.connection_config.mesycontrol_port = self.spin_mesycontrol_port.value()

        super(ConnectDialog, self).accept()

class MainWindow(QtGui.QMainWindow):
    def __init__(self, parent = None):
        super(MainWindow, self).__init__(parent)
        QtCore.QCoreApplication.instance().aboutToQuit.connect(self.on_qapp_quit)
        uic.loadUi(application_registry.instance.find_data_file('mesycontrol/ui/mainwin.ui'), self)

        self._device_windows = {}

        self.setup_tree_view = setup_treeview.SetupTreeView(parent=self)
        self.setup_tree_view.sig_open_device.connect(self._slt_open_device_window)
        self.setup_tree_view.sig_close_mrc.connect(self._slt_close_mrc)
        application_registry.instance.mrc_added.connect(self.setup_tree_view.model().add_mrc)
        self._add_subwindow(self.setup_tree_view, "Device Tree")

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

        connection       = mrc_connection.factory(config=dialog.connection_config)
        model            = hw_model.MRCModel()
        # FIXME: depends on the connection type! factory for this!
        model.controller = mrc_controller.MesycontrolMRCController(connection, model)
        application_registry.instance.register_mrc_model(model)

        mrc = app_model.MRC(mrc_model=model)
        application_registry.instance.register_mrc(mrc)
        connection.connect()

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
                mrc_command.RefreshMemory(device).start()

        subwin = self._device_windows[device]
        subwin.show()
        subwin.widget().show()
        self.mdiArea.setActiveSubWindow(subwin)

    def _slt_close_mrc(self, mrc):
        mrc.disconnect()
        self.setup_tree_view.model().remove_mrc(mrc)
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
            config = config_xml.parse_file(filename)
        except IOError as e:
            QtGui.QMessageBox.critical(self, "Error", "Reading from %s failed: %s" % (filename, e))
            return

        try:
            setup_loader = SetupLoader(config)

            pd = QtGui.QProgressDialog(self)
            pd.setMaximum(len(setup_loader))
            pd.setValue(0)

            def update_progress(current, total):
                pd.setMaximum(total)
                pd.setValue(current)

            setup_loader.progress_changed.connect(update_progress)
            setup_loader.stopped.connect(pd.close)
            setup_loader.start()
            pd_result = pd.exec_()
            if pd_result == 0:
                setup_loader.stop()
            setup_loader.get_result()
            QtGui.QMessageBox.information(self, "Info", "Setup loaded from %s" % filename)
        except Exception as e:
            QtGui.QMessageBox.critical(self, "Error", "Setup loading failed: %s" % e)

    @pyqtSlot()
    def on_actionSave_Setup_triggered(self):
        filename = QtGui.QFileDialog.getSaveFileName(self, "Save setup as",
                filter="XML files (*.xml);; *")

        if not len(filename):
            return

        setup_builder = SetupBuilder()
        for conn in self.app_model.mrc_connections:
            setup_builder.add_mrc(conn.mrc_model)

        pd = QtGui.QProgressDialog(self)
        pd.setMaximum(len(setup_builder))
        pd.setValue(0)

        def update_progress(current, total):
            pd.setValue(current)

        setup_builder.progress_changed.connect(update_progress)
        setup_builder.stopped.connect(pd.close)
        setup_builder.start()
        pd.exec_()

        if setup_builder.has_failed():
            QtGui.QMessageBox.critical(self, "Error", "Setup building failed")
        else:
            try:
                config = setup_builder.get_result()
                with open(filename, 'w') as f:
                    config_xml.write_file(config, f)
            except IOError as e:
                QtGui.QMessageBox.critical(self, "Error", "Writing to %s failed: %s" % (filename, e))
            else:
                QtGui.QMessageBox.information(self, "Info", "Configuration written to %s" % filename)

def signal_handler(signum, frame):
    logging.info("Received signal %s. Quitting...",
            signal.signum_to_name.get(signum, "%d" % signum))
    QtGui.QApplication.quit()

if __name__ == "__main__":
    # Logging setup
    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    logging.getLogger("mesycontrol.tcp_client").setLevel(logging.DEBUG)
    logging.getLogger("PyQt4.uic").setLevel(logging.INFO)

    # Signal handling
    signal.signum_to_name = dict((getattr(signal, n), n)
            for n in dir(signal) if n.startswith('SIG') and '_' not in n)
    signal.signal(signal.SIGINT, signal_handler)

    application_registry.instance = application_registry.ApplicationRegistry(
            sys.executable if getattr(sys, 'frozen', False) else __file__)

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
