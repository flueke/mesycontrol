#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from mesycontrol.protocol import Message
from PyQt4 import QtCore
from PyQt4 import QtNetwork
from PyQt4.QtCore import pyqtSignal
import logging
import Queue
import struct

class TCPClient(QtCore.QObject):
  sig_connecting       = pyqtSignal(str, int)
  sig_connected        = pyqtSignal(str, int)
  sig_disconnected     = pyqtSignal(str, int)
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

    self.log = logging.getLogger("TCPClient")

  def connect(self, host, port):
    self.disconnect()
    self.host = str(host)
    self.port = int(port)
    self.sig_connecting.emit(host, port)
    self.log.info("Connecting to %s:%d", self.host, self.port)
    self.socket.connectToHost(host, port)

  def disconnect(self):
    if self.socket.state() != QtNetwork.QAbstractSocket.UnconnectedState:
      self.socket.disconnectFromHost()
      if self.socket.state() != QtNetwork.QAbstractSocket.UnconnectedState:
        self.socket.waitForDisconnected()

  def is_connected(self):
    return self.socket.state() == QtNetwork.QAbstractSocket.ConnectedState

  def queue_request(self, message):
    self.log.debug("Queueing message %s", message)
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
        msg_data = message.serialize()
        data = struct.pack('!H', len(msg_data)) + msg_data
        self.log.debug("Writing message %s (size=%d)", message, len(data))
        self.socket.write(data)
      except Queue.Empty:
        self.log.debug("Message queue is empty")
        logging.debug("TCPClient: message queue is empty")
        return

  def _slt_socket_bytesWritten(self, n_bytes):
      pass

  def _slt_socket_readyRead(self):
    if self._response_size is None and self.socket.bytesAvailable() >= 2:
      self._response_size = struct.unpack('!H', self.socket.read(2))[0]

    if self._response_size is not None and self.socket.bytesAvailable() >= self._response_size:
      response_data = self.socket.read(self._response_size)
      message = Message.deserialize(response_data)
      self._response_size = None
      self._request_in_progress = False
      self.log.debug("Received message %s", message)
      self.sig_message_received.emit(message)
# FIXME: buggy reading/writing/response != notifcation crap. need to match requests to responses!
# should record the current request, wait for a reply and clear the current
# request once the reply was received
      self._slt_socket_readyRead()
      if not self._request_queue.empty():
        self._start_write_message()
      else:
        self.sig_queue_empty.emit()

  def _slt_connected(self):
    self.log.info("TCPClient: connected to %s:%d" % (self.host, self.port))
    self.sig_connected.emit(self.host, self.port)
    self._start_write_message()

  def _slt_disconnected(self):
    self.log.info("TCPClient: disconnected from %s:%d" % (self.host, self.port))
    logging.debug("TCPClient %s:%d: max request queue size was %d" %
            (self.host, self.port, self._max_queue_size))
    self.sig_disconnected.emit(self.host, self.port)
    self.host = self.port = None
    self._request_queue = Queue.Queue()
    self._max_queue_size = 0
    self._write_in_progress = False
    self._response_size = None

  def _slt_socket_error(self, socket_error):
    logging.error("TCPClient %s:%d: %s" % (self.host, self.port, self.socket.errorString()))
    self.sig_socket_error.emit(socket_error)

