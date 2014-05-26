#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

# - UIs for known devices (MHV4, MSCF16)
# - Device descriptions used to read and write config files

import logging
import os
import signal
import sys
from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSlot
from PyQt4.Qt import Qt
import mesycontrol.util
from mesycontrol import config_xml
from mesycontrol import application_model
from mesycontrol import mrc_connection
from mesycontrol.application_model import MRCModel
from mesycontrol.mrc_treeview import MRCTreeView
from mesycontrol.generic_device_widget import GenericDeviceWidget
from mesycontrol.util import find_data_file
from mesycontrol.setup import SetupBuilder, SetupLoader

class MainWindow(QtGui.QMainWindow):
    def __init__(self, parent = None):
        super(MainWindow, self).__init__(parent)
        QtCore.QCoreApplication.instance().aboutToQuit.connect(self.on_qapp_quit)
        uic.loadUi(find_data_file('ui/mainwin.ui'), self)
        self.app_model = application_model.instance
        self.mrc_tree  = MRCTreeView(self)
        self.mrc_tree.sig_open_device_window.connect(self._slt_open_device_window)
        self._add_subwindow(self.mrc_tree, "Device Tree")
        self.app_model.sig_connection_added.connect(self.mrc_tree.slt_connection_added)
        self._device_windows = {}

    def on_qapp_quit(self):
        logging.info("Exiting...")
        self.app_model.shutdown()

    @pyqtSlot()
    def on_actionConnect_triggered(self):
        text, ok = QtGui.QInputDialog.getText(self, "Connect to MRC", "device@baud or host:port",
                text = "/dev/ttyUSB0@115200")

        if not ok:
            return

        mrc_serial_port = mrc_baud_rate = None
        mrc_host = mrc_port = None
        text  = str(text)
        parts = text.split('@')

        if len(parts) == 2:
            mrc_serial_port = parts[0]
            mrc_baud_rate   = parts[1]

        parts = text.split(':')

        if len(parts) == 2:
            mrc_host = parts[0]
            mrc_port = parts[1]

        connection = mrc_connection.factory(
                serial_port=mrc_serial_port, baud_rate=mrc_baud_rate,
                host=mrc_host, port=mrc_port)

        self.app_model.registerConnection(connection)
        connection.connect()

    @pyqtSlot()
    def on_actionDisconnect_triggered(self):
        print "on_actionDisconnect_triggered"

    @pyqtSlot()
    def on_actionConnectToServer_triggered(self):
        text, ok = QtGui.QInputDialog.getText(self, "Connect to mesycontrol server", "host:port",
                text = "localhost:23000")

        if not ok:
            return

        parts = text.split(':')
        host  = parts[0]
        port  = int(parts[1])
        connection = mrc_connection.factory(mesycontrol_host=host, mesycontrol_port=port)
        self.app_model.registerConnection(connection)
        connection.connect()

    def _add_subwindow(self, widget, title):
        subwin = self.mdiArea.addSubWindow(widget)
        subwin.setWindowTitle(title)
        subwin.setAttribute(Qt.WA_DeleteOnClose, False)
        subwin.show()
        return subwin

    def _slt_open_device_window(self, device_model):
        key = (device_model.mrc_model, device_model.bus, device_model.dev)
        if not self._device_windows.has_key(key):
            widget = GenericDeviceWidget(device_model, self)
            title  = "%s %d.%d" % (device_model.mrc_model.connection.get_info(),
                    device_model.bus, device_model.dev)
            self._device_windows[key] = self._add_subwindow(widget, title)

        subwin = self._device_windows[key]
        subwin.show()
        subwin.widget().show()
        self.mdiArea.setActiveSubWindow(subwin)

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
            pd.exec_()
        except Exception as e:
            QtGui.QMessageBox.critical(self, "Error", "Setup loading failed: %s" % e)
        else:
            if setup_loader.has_failed():
                QtGui.QMessageBox.critical(self, "Error", "Setup loading failed")
            else:
                QtGui.QMessageBox.information(self, "Info", "Setup loaded from %s" % filename)

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

def find_data_dir():
    if getattr(sys, 'frozen', False):
        exe = sys.executable
        while os.path.islink(exe):
            lnk = os.readlink(exe)
            if os.path.isabs(lnk):
                exe = lnk
            else:
                exe = os.path.abspath(os.path.join(os.path.dirname(exe), lnk))
        return os.path.dirname(exe)
    else:
        return os.path.dirname(__file__)

if __name__ == "__main__":
    # Logging setup
    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    #logging.getLogger("TCPClient").setLevel(logging.INFO)
    #logging.getLogger("MRCModel").setLevel(logging.INFO)
    logging.getLogger("PyQt4.uic").setLevel(logging.INFO)

    # Signal handling
    signal.signum_to_name = dict((getattr(signal, n), n)
            for n in dir(signal) if n.startswith('SIG') and '_' not in n)
    signal.signal(signal.SIGINT, signal_handler)

    # Binary directory needed to locate the server binary.
    application_model.instance.bin_dir = os.path.abspath(os.path.dirname(
        sys.executable if getattr(sys, 'frozen', False) else __file__))

    # Path to the directory where ui, xml and other datafiles are stored.
    application_model.instance.data_dir = find_data_dir()

    # Load system device descriptions
    application_model.instance.load_system_descriptions()

    app = QtGui.QApplication(sys.argv)

    # Let the interpreter run every 500 ms to be able to react to signals
    # arriving from the OS.
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    # Confine garbage collection to the main thread to avoid crashes.
    garbage_collector = mesycontrol.util.GarbageCollector(debug=False)

    mainwin = MainWindow()
    mainwin.show()
    ret = app.exec_()

    del mainwin
    del garbage_collector

    sys.exit(ret)
