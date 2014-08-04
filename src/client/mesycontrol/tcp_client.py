#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from mesycontrol.protocol import Message, MessageError
from PyQt4 import QtCore
from PyQt4 import QtNetwork
from PyQt4.QtCore import pyqtSignal, pyqtProperty, pyqtSlot
import struct
import util

class Stats:
    def __init__(self):
        self.tx_queue_max_size = 0
        self.messages_sent        = 0
        self.messages_received    = 0
        self.bytes_sent           = 0
        self.bytes_received       = 0
        self.send_histo           = {}
        self.receive_histo        = {}

    def update_write_queue_size(self, sz):
        self.tx_queue_max_size = max(self.tx_queue_max_size, sz)

    def message_sent(self, msg, wire_size):
        self.messages_sent += 1
        self.bytes_sent += wire_size
        t = msg.get_type_name()
        self.send_histo[t] = self.send_histo.get(t, 0) + 1

    def message_received(self, msg, wire_size):
        self.messages_received += 1
        self.bytes_received   += wire_size
        t = msg.get_type_name()
        self.receive_histo[t] = self.receive_histo.get(t, 0) + 1

class TCPClient(QtCore.QObject):
    sig_connecting        = pyqtSignal()
    sig_connected         = pyqtSignal()
    sig_disconnected      = pyqtSignal()
    sig_socket_error      = pyqtSignal(int, str)

    sig_message_sent      = pyqtSignal(Message)          #: message
    sig_message_received  = pyqtSignal(Message)          #: message
    sig_response_received = pyqtSignal(Message, Message) #: request, response
    sig_tx_queue_empty    = pyqtSignal()

    def __init__(self, parent=None):
        super(TCPClient, self).__init__(parent)

        self.log   = util.make_logging_source_adapter(__name__, self)
        self._host = None
        self._port = None
        self._write_queue = list()
        self._reset_state()

        self._socket = QtNetwork.QTcpSocket(self)
        self._socket.connected.connect(self._slt_connected)
        self._socket.disconnected.connect(self._slt_disconnected)
        self._socket.error.connect(self._slt_socket_error)
        self._socket.bytesWritten.connect(self._slt_socket_bytesWritten)
        self._socket.readyRead.connect(self._slt_socket_readyRead)

    def _reset_state(self):
        self._current_request = None
        self._current_response_handler = None
        self._current_write_data = None
        self._read_size = 0
        self._stats = Stats()

    def get_host(self): return self._host
    def get_port(self): return self._port
    def get_stats(self): return self._stats

    host  = pyqtProperty(str, get_host)
    port  = pyqtProperty(int, get_port)
    stats = pyqtProperty(object, get_stats)

    def connect(self, host, port):
        self.disconnect()
        self._reset_state()
        self._host = str(host)
        self._port = int(port)
        self.sig_connecting.emit()
        self.log.info("Connecting to %s:%d", self.host, self.port)
        self._socket.connectToHost(self.host, self.port)

    def disconnect(self):
        if self._socket.state() != QtNetwork.QAbstractSocket.UnconnectedState:
          self._socket.disconnectFromHost()
          if self._socket.state() != QtNetwork.QAbstractSocket.UnconnectedState:
            self._socket.waitForDisconnected()

    def is_connected(self):
        return self._socket.state() == QtNetwork.QAbstractSocket.ConnectedState

    def is_connecting(self):
        return self._socket.state() in (QtNetwork.QAbstractSocket.ConnectingState,
                QtNetwork.QAbstractSocket.HostLookupState)

    def request_in_progress(self):
        return self._current_request is not None

    def queue_request(self, request, response_handler=None):
        """Adds the given request to the outgoing queue. Once the request has
        been sent and a response is received the given response handler will be
        invoked.
        Returns a unique identifier that can be used to remove the request from
        the queue using cancel_request().
        """
        was_empty = len(self._write_queue) == 0
        tup = (request, response_handler)
        self.log.debug("Queueing request %s, response_handler=%s, id=%d", request, response_handler, id(tup))
        self._write_queue.append(tup)
        self.log.debug("Write queue size = %d", self.get_write_queue_size())
        self.stats.update_write_queue_size(self.get_write_queue_size())
        if was_empty:
            self._start_write_message()
        return id(tup)

    def cancel_request(self, request_id):
        try:
            tup = filter(lambda t: id(t) == request_id, self._write_queue)[0]
            self.log.debug("Canceling request %s, response_handler=%s, id=%d", tup[0], tup[1], id(tup))
            self._write_queue.remove(tup)
            return True
        except IndexError:
            return False

    def get_write_queue_size(self):
        return len(self._write_queue)

    def _start_write_message(self):
        if not self.is_connected() or self.request_in_progress():
            return

        try:
            self._current_request, self._current_response_handler = self._write_queue.pop(0)
            msg_data = self._current_request.serialize()
            self._current_write_data = struct.pack('!H', len(msg_data)) + msg_data
            self.log.debug("Writing message %s (size=%d)", self._current_request, len(self._current_write_data))
            self._socket.write(self._current_write_data)
        except IndexError:
            self.log.debug("Message queue is empty")
            return

    def _slt_socket_bytesWritten(self, n_bytes):
        self.stats.message_sent(self._current_request, len(self._current_write_data))
        self.sig_message_sent.emit(self._current_request)

    def _slt_socket_readyRead(self):
        if self._read_size <= 0 and self._socket.bytesAvailable() >= 2:
            self._read_size = struct.unpack('!H', self._socket.read(2))[0]
            self.log.debug("Incoming message size=%d", self._read_size)

        if self._read_size > 0 and self._socket.bytesAvailable() >= self._read_size:
            message_data = self._socket.read(self._read_size)
            try:
                message = Message.deserialize(message_data)
            except MessageError as e:
                self.log.error("Could not deserialize incoming message: %s. Disconnecting...", e)
                self.disconnect()
                return

            self.log.debug("Received message %s", message)

            self.stats.message_received(message, self._read_size + 2)
            self.sig_message_received.emit(message)
            self._read_size = 0

            if message.is_response():
                self.sig_response_received.emit(self._current_request, message)

                if self._current_response_handler is not None:
                    self._current_response_handler(self._current_request, message)

                self._current_request = None
                self._current_response_handler = None

                # The response to the last message was received. Start sending
                # the next message or signal that the queue is empty.
                if len(self._write_queue) > 0:
                    self._start_write_message()
                else:
                    self.sig_tx_queue_empty.emit()

            if self._socket.bytesAvailable() >= 2:
                # Handle additional available data.
                self._slt_socket_readyRead()

    @pyqtSlot()
    def _slt_connected(self):
        self.log.info("Connected to %s:%d" % (self.host, self.port))
        self.sig_connected.emit()
        self._start_write_message()

    @pyqtSlot()
    def _slt_disconnected(self):
        self.log.info("Disconnected from %s:%d" % (self.host, self.port))
        self.log.info("socket.errorString()=%s" % self._socket.errorString())

        stats = self.stats
        self.log.debug("%d messages sent (%d bytes)" %
                (stats.messages_sent, stats.bytes_sent))

        self.log.debug("%d messages received (%d bytes)" %
                (stats.messages_received, stats.bytes_received))

        self.log.debug("Send histo: %s" % stats.send_histo)
        self.log.debug("Recv histo: %s" % stats.receive_histo)

        self.sig_disconnected.emit()

    @pyqtSlot(int)
    def _slt_socket_error(self, socket_error):
        self.log.error("%s:%d: %s" % (self.host, self.port, self._socket.errorString()))
        self.sig_socket_error.emit(socket_error, self._socket.errorString())

