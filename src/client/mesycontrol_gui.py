#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

# Wishlist:
# - Connect to server
# - Scanbus
# - List of devices
# - Generic device UI
# - UIs for known devices (MHV4, MSCF16)
# - Device descriptions used to read and write config files

# Design:
# - QMainWindow with QMdiArea as the central widget
# - TCPClient class communicating via signals and slots
#   signals: parameterRead, parameterSet, busScanned, connecting, connected, disconnected
# - Device representation:
#   Dictionary mapping parameter addresses to Parameter Objects
# - Parameter Object:
#   Device backreference, address, value, poll_enabled, read_only, alias, ...

# Global objects:
# - TCPClient
# - MRCModel
#   Knows the tcp_client
#   Keeps track of information gathered from the mrc1.
#   
#   bus_data: IDC and RC info by bus and dev
#   device_memory: maps bus -> dev -> par -> value  (Value could contain more data like timestamps, etc.)
#   device_mirror: maps bus -> dev -> par -> value
#   scanbus(self, bus)
#   read(self, bus, dev, par)
#   read_mirror(self, bus, dev, par)
#   set(self, bus, dev, par, val)
#   _slt_message_received(self, msg):
#     update bus_data and/or device_values depending on the message
#     emit bus_data_changed(bus, dev)
#     emit device_value_changed(bus, dev, par)


import logging
import os
import Queue
import signal
import struct
import sys
from PyQt4 import QtCore, QtGui, QtNetwork, uic
from PyQt4.QtCore import pyqtSignal
from PyQt4.Qt import Qt
from mesycontrol.protocol import Message

def find_data_file(filename):
   if getattr(sys, 'frozen', False):
      exe = sys.executable
      while os.path.islink(exe):
         exe = os.path.abspath(os.path.join(os.path.dirname(exe), os.readlink(exe)))
      datadir = os.path.dirname(exe)
   else:
      datadir = os.path.dirname(__file__)

   return os.path.join(datadir, filename)

class TCPClient(QtCore.QObject):
  sig_connecting       = pyqtSignal('QString', int)
  sig_connected        = pyqtSignal('QString', int)
  sig_disconnected     = pyqtSignal('QString', int)
  sig_socket_error     = pyqtSignal(int)
  sig_message_received = pyqtSignal(object)
  sig_queue_empty      = pyqtSignal()

  def __init__(self, parent = None):
    super(TCPClient, self).__init__(parent)
    self.host = self.port = None
    self._request_queue = Queue.Queue()
    self._request_in_progress = False
    self._response_size = None
    self._max_queue_size = 0

    self.socket = QtNetwork.QTcpSocket(self)
    self.socket.connected.connect(self._slt_connected)
    self.socket.disconnected.connect(self._slt_disconnected)
    self.socket.error.connect(self._slt_socket_error)
    self.socket.bytesWritten.connect(self._slt_socket_bytesWritten)
    self.socket.readyRead.connect(self._slt_socket_readyRead)

  def __del__(self):
    logging.debug("TCPClient: max request queue size was %d" % self._max_queue_size)

  def connect(self, host, port):
    self.disconnect()
    self.host = host
    self.port = port
    self.sig_connecting.emit(host, port)
    self.socket.connectToHost(host, port)

  def disconnect(self):
    if self.is_connected():
      self.socket.disconnectFromHost()
      if self.socket.state() != QtNetwork.QAbstractSocket.UnconnectedState:
        self.socket.waitForDisconnected()

  def is_connected(self):
    return self.socket.state() == QtNetwork.QAbstractSocket.ConnectedState

  def queue_request(self, message):
    was_empty = self._request_queue.empty()
    self._request_queue.put(message)
    self._max_queue_size = max(self._max_queue_size, self.get_request_queue_size())
    if was_empty:
      self._start_write_message()

  def get_request_queue_size(self):
    return self._request_queue.qsize()

  def _start_write_message(self):
    if self.is_connected() and not self._request_in_progress:
      try:
        message = self._request_queue.get(False)
        self._request_in_progress = True
        logging.debug("TCPClient: writing message: %s" % message)
        msg_data = message.serialize()
        data = struct.pack('!H', len(msg_data)) + msg_data
        self.socket.write(data)
      except Queue.Empty:
        logging.debug("TCPClient: message queue is empty")
        return

  def _slt_socket_bytesWritten(self, n_bytes):
    pass

  def _slt_socket_readyRead(self):
    if self._response_size is None and self.socket.bytesAvailable() >= 2:
      self._response_size = struct.unpack('!H', self.socket.read(2))[0]

    if self._response_size is not None and self.socket.bytesAvailable() >= self._response_size:
      # TODO: add and catch Message.deserialize() exceptions
      response_data = self.socket.read(self._response_size)
      message = Message.deserialize(response_data)
      self._response_size = None
      self._request_in_progress = False
      logging.debug("TCPClient: received message: %s" % message)
      self.sig_message_received.emit(message)
      if not self._request_queue.empty():
        self._start_write_message()
      else:
        self.sig_queue_empty.emit()

  def _slt_connected(self):
    self.sig_connected.emit(self.host, self.port)

  def _slt_disconnected(self):
    self.sig_disconnected.emit(self.host, self.port)
    self.host = self.port = None
    self._request_queue = Queue.Queue()
    self._write_in_progress = False
    self._response_size = None

  def _slt_socket_error(self, socket_error):
    logging.error("TCPClient %s:%d: %s" % (self.host, self.port, self.socket.errorString()))
    self.sig_socket_error.emit(socket_error)

class MRCModel(QtCore.QObject):
  # Emitted after a scanbus response has been received. The argument is the
  # complete bus_data dict.
  sig_bus_data_changed = pyqtSignal(dict)

  # Emitted after a value has been read or set. Args are bus, dev, par, value
  sig_parameter_value_changed = pyqtSignal(int, int, int, int)

  def __init__(self, mrc_client, parent = None):
    super(QtCore.QObject, self).__init__(parent)
    self.bus_data      = {}
    self.device_memory = {}
    self.poll_set      = set()

    for bus in range(2):
      self.bus_data[bus]      = {}
      self.device_memory[bus] = {}
      for dev in range(16):
        self.bus_data[bus][dev] = {'idc': None, 'rc': None}
        self.device_memory[bus][dev] = {}

    self.mrc_client = mrc_client
    self.mrc_client.sig_connected.connect(self._slt_client_connected)
    self.mrc_client.sig_message_received.connect(self._slt_message_received)
    self.mrc_client.sig_queue_empty.connect(self._slt_client_queue_empty)

  def scanbus(self, bus):
    self.mrc_client.queue_request(Message('request_scanbus', bus=bus))

  def read_parameter(self, bus, dev, par):
    self.mrc_client.queue_request(Message('request_read', bus=bus, dev=dev, par=par))

  def set_parameter(self, bus, dev, par, value):
    self.mrc_client.queue_request(Message('request_set', bus=bus, dev=dev, par=par, val=value))

  def set_rc(self, bus, dev, rc):
    self.mrc_client.queue_request(Message('request_rc_on' if rc else 'request_rc_off', bus=bus, dev=dev))

  def add_poll_parameter(self, bus, dev, par):
    self.poll_set.add((bus, dev, par))
    if self.mrc_client.get_request_queue_size() == 0:
      self._queue_poll_parameters()

  def remove_poll_parameter(self, bus, dev, par):
    self.poll_set.discard((bus, dev, par))

  def _slt_client_connected(self, host, port):
    print "Connected to %s:%d. Scanning busses." % (host, port)
    self.scanbus(0)
    self.scanbus(1)

  def _slt_message_received(self, msg):
    if msg.get_type_name() == 'response_scanbus':
      for dev in range(16):
        self.bus_data[msg.bus][dev] = {'idc': msg.bus_data[dev][0], 'rc': msg.bus_data[dev][1]}
        self.sig_bus_data_changed.emit(self.bus_data)

    elif msg.get_type_name() in ('response_read', 'response_set'):
      self.device_memory[msg.bus][msg.dev][msg.par] = msg.val
      self.sig_parameter_value_changed.emit(msg.bus, msg.dev, msg.par, msg.val)

  def _slt_client_queue_empty(self):
    self._queue_poll_parameters()

  def _queue_poll_parameters(self):
    for bus, dev, par in self.poll_set:
      self.read_parameter(bus, dev, par)

class MainWindow(QtGui.QMainWindow):
  def __init__(self, parent = None):
    super(MainWindow, self).__init__(parent)

    QtCore.QCoreApplication.instance().aboutToQuit.connect(self.on_qapp_quit)

    # load the ui
    uic.loadUi(find_data_file('ui/mainwin.ui'), self)

    self.client = TCPClient()
    self.client.connect('localhost', 23000)

    self.mrc_model = MRCModel(self.client)
    self.bus_widget = BusWidget(self.mrc_model, self)
    self.bus_widget.sig_open_device_window.connect(self._slt_open_device_window)
    self._add_subwindow(self.bus_widget, "Bus Info")
    self._device_windows = {0:{}, 1:{}}


  def on_qapp_quit(self):
    self.client.disconnect()

  def _add_subwindow(self, widget, title):
    subwin = self.mdiArea.addSubWindow(widget)
    subwin.setWindowTitle(title)
    subwin.setAttribute(Qt.WA_DeleteOnClose, False)
    subwin.show()
    return subwin

  def _slt_open_device_window(self, bus, dev):
    if not self._device_windows[bus].has_key(dev):
      widget = GenericDeviceWidget(bus, dev, self.mrc_model, self)
      self._device_windows[bus][dev] = self._add_subwindow(widget, "%d:%d" % (bus, dev))

    subwin = self._device_windows[bus][dev]
    subwin.show()
    subwin.widget().show()
    self.mdiArea.setActiveSubWindow(subwin)

class BusWidget(QtGui.QWidget):
  sig_open_device_window = pyqtSignal(int, int)

  def __init__(self, mrc_model, parent = None):
    super(BusWidget, self).__init__(parent)
    self.mrc_model   = mrc_model
    self.tree_widget = QtGui.QTreeWidget(self)
    self.tree_widget.setHeaderLabels(['Bus/Dev', 'Device ID', 'RC Status'])
    self.tree_widget.itemDoubleClicked.connect(self._slt_item_doubleclicked)

    for bus in range(2):
      bus_root = QtGui.QTreeWidgetItem(self.tree_widget)
      bus_root.setText(0, str(bus))
      for dev in range(16):
        QtGui.QTreeWidgetItem(bus_root)

    self._slt_bus_data_changed(self.mrc_model.bus_data)
    self.mrc_model.sig_bus_data_changed.connect(self._slt_bus_data_changed)

    scanbus_button = QtGui.QPushButton("Scanbus")
    scanbus_button.clicked.connect(self._slt_scanbus_button_clicked)

    layout = QtGui.QVBoxLayout()
    layout.addWidget(scanbus_button)
    layout.addWidget(self.tree_widget)
    self.setLayout(layout)

  def _slt_bus_data_changed(self, bus_data):
    for bus in range(2):
      bus_root = self.tree_widget.topLevelItem(bus)
      for dev in range(16):
        idc = bus_data[bus][dev]['idc']

        idc_text = '-'
        if idc is None:
          idc_text = '<?>'
        elif idc > 0:
          idc_text = str(idc)

        rc = bus_data[bus][dev]['rc']

        rc_text = 'off'
        if rc is None:
          rc_text = '<?>'
        elif rc:
          rc_text = 'on'

        dev_item = bus_root.child(dev)
        dev_item.setText(0, str(dev))
        dev_item.setText(1, idc_text)
        dev_item.setText(2, rc_text)
        dev_item.mrc_bus_data = { 'bus': bus, 'dev': dev, 'idc': idc, 'rc': rc }

  def _slt_item_doubleclicked(self, item, column):
    if not hasattr(item, 'mrc_bus_data'):
      return

    bus = item.mrc_bus_data['bus']
    dev = item.mrc_bus_data['dev']
    rc  = item.mrc_bus_data['rc']

    if column == 1 and item.mrc_bus_data['idc'] > 0:
      self.sig_open_device_window.emit(bus, dev)

    elif column == 2 and item.mrc_bus_data['idc'] > 0:
      self.mrc_model.set_rc(bus, dev, not rc)
      self.mrc_model.scanbus(bus)

  def _slt_scanbus_button_clicked(self):
    self.mrc_model.scanbus(0)
    self.mrc_model.scanbus(1)

class GenericDeviceWidget(QtGui.QWidget):
  def __init__(self, bus, dev, mrc_model, parent = None):
    super(GenericDeviceWidget, self).__init__(parent)
    self.bus = bus
    self.dev = dev
    self.mrc_model = mrc_model
    self.mrc_model.sig_parameter_value_changed.connect(self._slt_parameter_value_changed)

    self.table_widget = QtGui.QTableWidget(256, 3)
    self.table_widget.setHorizontalHeaderLabels(['Address', 'Value', 'Set Value'])
    self.table_widget.verticalHeader().hide()
    layout = QtGui.QHBoxLayout()
    layout.addWidget(self.table_widget)
    self.setLayout(layout)

    device_memory = self.mrc_model.device_memory[self.bus][self.dev]

    for addr in range(256):
      self.table_widget.setItem(addr, 0, QtGui.QTableWidgetItem(str(addr)))
      self.table_widget.item(addr, 0).setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)

      self.table_widget.setItem(addr, 1, QtGui.QTableWidgetItem())
      self.table_widget.item(addr, 1).setFlags(Qt.ItemIsSelectable|Qt.ItemIsUserCheckable|Qt.ItemIsEnabled)
      self.table_widget.item(addr, 1).setCheckState(Qt.Unchecked)

      self.table_widget.setItem(addr, 2, QtGui.QTableWidgetItem())

      if device_memory.has_key(addr):
        self.table_widget.item(addr, 1).setText(str(device_memory[addr]))
        self.table_widget.item(addr, 2).setText(str(device_memory[addr]))

    self.table_widget.resizeColumnsToContents()
    self.table_widget.resizeRowsToContents()

    self.table_widget.itemChanged.connect(self._slt_table_item_changed)

    for addr in range(256):
      if not device_memory.has_key(addr):
        self.mrc_model.read_parameter(self.bus, self.dev, addr)

  def _slt_parameter_value_changed(self, bus, dev, addr, value):
    if bus == self.bus and dev == self.dev:
      self.table_widget.item(addr, 1).setText(str(value))

  def _slt_table_item_changed(self, item):
    if item.column() == 1:
      if item.checkState() == Qt.Checked:
        self.mrc_model.add_poll_parameter(self.bus, self.dev, item.row())
      else:
        self.mrc_model.remove_poll_parameter(self.bus, self.dev, item.row())

    elif item.column() == 2:
      try:
        int_val = int(item.text())
        if 0 <= int_val and int_val <= 65535:
          self.mrc_model.set_parameter(self.bus, self.dev, item.row(), int_val)
      except ValueError:
        print "invalid value given!"

def signal_handler(*args):
  print "signal handler"
  QtGui.QApplication.quit()

if __name__ == "__main__":
  logging.basicConfig(level=logging.DEBUG, format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

  signal.signal(signal.SIGINT, signal_handler)
  app = QtGui.QApplication(sys.argv)
  mainwin = MainWindow()
  mainwin.show()
  sys.exit(app.exec_())
