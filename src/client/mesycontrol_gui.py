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
from mesycontrol.tcp_client import TCPClient
from mesycontrol.server_process import ServerProcess
from mesycontrol import application_model
from mesycontrol.application_model import MRCModel
from mesycontrol.mrc_treeview import MRCTreeView
from mesycontrol.generic_device_widget import GenericDeviceWidget
from mesycontrol.util import find_data_file

class MRCConnection(QtCore.QObject):
    def __init__(self,
            mrc_serial_port=None, mrc_baud_rate=None,
            mrc_host=None, mrc_port=None,
            server_host=None, server_port=None,
            parent=None):

        super(MRCConnection, self).__init__(parent)

        self.server_process = None
        if mrc_serial_port is not None or mrc_host is not None:
            self.server_process                 = ServerProcess(self)
            self.server_process.mrc_serial_port = str(mrc_serial_port)
            self.server_process.mrc_baud_rate   = int(mrc_baud_rate)
            self.server_process.mrc_host        = str(mrc_host)
            self.server_process.mrc_port        = int(mrc_port)
            self.server_process.sig_started.connect(self._slt_server_process_started)
            self.server_process.sig_finished.connect(self._slt_server_process_finished)

            self.server_start_timer = QtCore.QTimer(self)
            self.server_start_timer.setSingleShot(True)
            self.server_start_timer.setInterval(1000)
            self.server_start_timer.timeout.connect(self._slt_server_start_timer_timeout)
        elif server_host is not None:
            self.server_host = str(server_host)
            self.server_port = int(server_port)

        self.tcp_client                     = TCPClient(self)
        self.mrc_model                      = MRCModel(self, self)

    def get_mrc_address_string(self):
        if self.server_process is not None:
            return self.server_process.get_mrc_address_string()
        else:
            return "%s:%d" % (self.server_host, self.server_port)

    def start(self):
        if self.server_process is not None and not self.server_process.is_running():
            self.server_process.start()
        elif self.server_process is None and self.tcp_client.host is None:
            self.tcp_client.connect(self.server_host, self.server_port)

    def stop(self):
        self.tcp_client.disconnect()
        if self.server_process is not None:
            self.server_process.stop()

    def info_string(self):
        if self.server_process is not None:
            if self.server_process.mrc_serial_port is not None:
                return "%s@%d" % (self.server_process.mrc_serial_port, self.server_process.mrc_baud_rate)

            if self.server_process.mrc_host is not None:
                return "%s:%d" % (self.server_process.mrc_host, self.server_process.mrc_port)
        elif self.server_host is not None:
            return "mesycontrol_server %s:%d" % (self.server_host, self.server_port)

        return "<unknown>"

    def _slt_server_process_started(self):
        if self.server_process.is_running():
            self.server_start_timer.start()


    def _slt_server_start_timer_timeout(self):
        if self.server_process.is_running():
            self.tcp_client.connect(self.server_process.listen_address, self.server_process.listen_port)

    def _slt_server_process_finished(self, code, status):
        if self.server_process.get_exit_code_string() == "exit_address_in_use":
            self.server_process.listen_port += 1
            self.stop()
            self.start()

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
        print "on_qapp_quit"
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

        mrc_connection = MRCConnection(mrc_serial_port, mrc_baud_rate, mrc_host, mrc_port)
        self.app_model.registerConnection(mrc_connection)
        mrc_connection.start()

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
        mrc_connection = MRCConnection(server_host=host, server_port=port)
        self.app_model.registerConnection(mrc_connection)
        mrc_connection.start()

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
            title  = "%s %d.%d" % (device_model.mrc_model.connection.info_string(), device_model.bus, device_model.dev)
            self._device_windows[key] = self._add_subwindow(widget, title)

        subwin = self._device_windows[key]
        subwin.show()
        subwin.widget().show()
        self.mdiArea.setActiveSubWindow(subwin)


def signal_handler(*args):
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
    # Binary directory needed to locate the server binary.
    application_model.instance.bin_dir = os.path.abspath(os.path.dirname(
        sys.executable if getattr(sys, 'frozen', False) else __file__))

    # Path to the directory where ui, xml and other datafiles are stored.
    application_model.instance.data_dir = find_data_dir()

    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    signal.signal(signal.SIGINT, signal_handler)

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
