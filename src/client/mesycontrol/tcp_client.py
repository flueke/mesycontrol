#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtProperty
from qt import pyqtSignal
from qt import QtCore
from qt import QtNetwork
import collections
import struct

from future import Future
import protocol
import util

class SocketError(Exception):
    def __init__(self, error_code, error_string):
        self.error_code   = int(error_code)
        self.error_string = str(error_string)

    def __str__(self):
        return self.error_string

    def __int__(self):
        return self.error_code

RequestResult = collections.namedtuple("RequestResult", "request response")

class MCTCPClient(QtCore.QObject):
    """Mesycontrol TCP client"""

    connected               = pyqtSignal()
    disconnected            = pyqtSignal()
    connecting              = pyqtSignal(str, int)
    socket_error            = pyqtSignal(object)   #: instance of SocketError

    request_queued          = pyqtSignal(object, object) #: request, Future
    request_sent            = pyqtSignal(object, object) #: request, Future
    message_received        = pyqtSignal(object)         #: Message
    response_received       = pyqtSignal(object, object, object) #: request, response, Future
    notification_received   = pyqtSignal(object) #: Message
    error_received          = pyqtSignal(object) #: Message

    queue_empty             = pyqtSignal()
    queue_size_changed      = pyqtSignal(int)

    def __init__(self, parent=None):
        super(MCTCPClient, self).__init__(parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self._queue = util.OrderedSet()
        self._socket = QtNetwork.QTcpSocket()
        self._socket.connected.connect(self.connected)
        self._socket.disconnected.connect(self.disconnected)
        self._socket.error.connect(self._socket_error)
        self._socket.readyRead.connect(self._socket_readyRead)
        self._reset_state()

    def _reset_state(self):
        self._current_request = None
        self._read_size = 0

    def connect(self, host, port):
        """Connect to the given host and port.
        Returns a Future that fullfills once the connection has been
        established or an errors occurs.
        Disconnects if the client currently is connected.
        """

        ret = Future()

        def do_connect():
            self.log.debug("Connecting to %s:%d", host, port)

            def dc():
                self._socket.connected.disconnect(socket_connected)
                self._socket.error.disconnect(socket_error)

            def socket_connected():
                self.log.debug("Connected to %s:%d", host, port)
                dc()
                ret.set_result(True)

            def socket_error(socket_error):
                dc()
                ret.set_exception(SocketError(socket_error, self._socket.errorString()))
                self.log.error("%s", ret.exception())

            self._reset_state()
            self._socket.connected.connect(socket_connected)
            self._socket.error.connect(socket_error)
            self._socket.connectToHost(host, port)
            self.connecting.emit(host, port)

        if self.is_connected() or self.is_connecting():
            self.disconnect().add_done_callback(do_connect)
        else:
            do_connect()

        return ret

    def disconnect(self):
        """Disconnect. Returns a Future that fullfills once the connection has
        been disconnected or an error occurs."""
        if self.is_disconnected():
            return Future().set_result(True)

        ret = Future()

        def dc():
            self._socket.disconnected.disconnect(socket_disconnected)
            self._socket.error.disconnect(socket_error)

        def socket_disconnected():
            dc()
            self._reset_state()
            ret.set_result(True)

        def socket_error(socket_error):
            dc()
            ret.set_exception(SocketError(socket_error, self._socket.errorString()))

        self._socket.disconnected.connect(socket_disconnected)
        self._socket.error.connect(socket_error)

        self._socket.disconnectFromHost()

        return ret

    def is_connected(self):
        """True if connected, False otherwise."""
        return self._socket.state() == QtNetwork.QAbstractSocket.ConnectedState

    def is_connecting(self):
        return self._socket.state() in (QtNetwork.QAbstractSocket.ConnectingState,
                QtNetwork.QAbstractSocket.HostLookupState)

    def is_disconnected(self):
        return self._socket.state() == QtNetwork.QAbstractSocket.UnconnectedState

    def is_busy(self):
        return self.is_connecting() or self.get_queue_size() > 0

    def is_idle(self):
        return self.is_connected() and self.get_queue_size() == 0

    def get_queue_size(self):
        return len(self._queue)

    def queue_request(self, request):
        """Adds the given request to the outgoing queue. Returns a Future that
        fullfills once a response is received or an error occurs."""
        was_empty = self.get_queue_size() == 0
        ret = Future()
        self._queue.add((request, ret))
        self.request_queued.emit(request, ret)
        self.queue_size_changed.emit(len(self._queue))
        if was_empty:
            self._start_write_request()
        return ret

    def _start_write_request(self):
        if not self.is_connected() or self._current_request is not None:
            self.log.debug("_start_write_request: not connected or request in progress")
            return

        request, future = self._current_request = self._queue.pop(False) # FIFO order
        self.queue_size_changed.emit(len(self._queue))
        data = request.serialize()
        data = struct.pack('!H', len(data)) + data # prepend message size
        self.log.debug("_start_write_request: writing %s (len=%d)", request, len(data))
        if self._socket.write(data) == -1:
            future.set_exception(SocketError(self._socket.error(), self._socket.errorString()))
        else:
            def bytes_written():
                self.log.debug("_start_write_request: request %s sent", request)
                self._socket.bytesWritten.disconnect(bytes_written)
                self.request_sent.emit(request, future)
            self._socket.bytesWritten.connect(bytes_written)

    def _socket_readyRead(self):
        if self._read_size <= 0 and self._socket.bytesAvailable() >= 2:
            self._read_size = struct.unpack('!H', self._socket.read(2))[0]
            self.log.debug("_socket_readyRead: incoming msg size = %d", self._read_size)

        if self._read_size > 0 and self._socket.bytesAvailable() >= self._read_size:
            message_data = self._socket.read(self._read_size)
            try:
                message = protocol.Message.deserialize(message_data)
                self.log.debug("_socket_readyRead: received %s", message)
            except protocol.MessageError as e:
                self.log.error("Could not deserialize incoming message: %s.", e)
                return

            self._read_size = 0
            self.message_received.emit(message)

            if message.is_response() or message.is_error():
                request, future = self._current_request

                if message.is_error():
                    future.set_exception(protocol.MessageError(
                        message.get_error_code(), message.get_error_string(), request))

                    self.error_received.emit(message)
                else:
                    future.set_result(RequestResult(request, message))

                self.response_received.emit(request, message, future)
                self._current_request = None

                if self.get_queue_size() > 0:
                    self._start_write_request()
                else:
                    self.queue_empty.emit()

            elif message.is_notification():
                self.notification_received.emit(message)

            if self._socket.bytesAvailable() >= 2:
                # Handle additional available data.
                self._socket_readyRead()

    def _socket_error(self, socket_error):
        self.socket_error.emit(SocketError(socket_error, self._socket.errorString()))
        self.disconnected.emit()

    def get_host(self):
        return self._socket.peerName()

    def get_port(self):
        return self._socket.peerPort()

    host = pyqtProperty(str, get_host)
    port = pyqtProperty(int, get_port)

