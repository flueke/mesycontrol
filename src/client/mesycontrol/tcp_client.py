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
        self._socket.disconnected.connect(self._socket_disconnected)
        self._socket.error.connect(self._socket_error)
        self._socket.readyRead.connect(self._socket_readyRead)
        self._current_request = None
        self._reset_state()

    def connect(self, host, port):
        """Connect to the given host and port.
        Returns a Future that fullfills once the connection has been
        established or an errors occurs.
        Disconnects if the client currently is connected.
        """

        self.log.debug("connect(): %s:%d", host, port)

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
                self.log.error("Error connecting to %s:%d: %s", host, port,
                        self._socket.errorString())
                dc()
                ret.set_exception(util.SocketError(socket_error, self._socket.errorString()))
                self.log.error("%s", ret.exception())

            self._reset_state()
            self._socket.connected.connect(socket_connected)
            self._socket.error.connect(socket_error)
            self._socket.connectToHost(host, port)
            self.log.debug("connect: emitting connecting")
            self.connecting.emit(host, port)

        if self.is_connected() or self.is_connecting():
            self.disconnect().add_done_callback(do_connect)
        else:
            do_connect()

        return ret

    def disconnect(self):
        """Disconnect. Returns a Future that fullfills once the connection has
        been disconnected or an error occurs."""

        self.log.debug("disconnect()")

        if self.is_disconnected():
            return Future().set_result(True)

        ret = Future()

        host, port = self.host, self.port

        def dc():
            self._socket.disconnected.disconnect(socket_disconnected)
            self._socket.error.disconnect(socket_error)

        def socket_disconnected():
            self.log.debug("Disconnected from %s:%d", host, port)
            dc()
            ret.set_result(True)

        def socket_error(socket_error):
            self.log.error("Socket error from %s:%d: %s", host, port,
                    self._socket.errorString())
            dc()
            ret.set_exception(util.SocketError(socket_error, self._socket.errorString()))

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
        ret = Future()

        if not self.is_connected():
            ret.set_exception(util.Disconnected())
            return ret

        was_empty = self.get_queue_size() == 0
        self._queue.add((request, ret))
        self.log.debug("Queueing request %s, queue size=%d", request, self.get_queue_size())
        self.request_queued.emit(request, ret)
        self.queue_size_changed.emit(self.get_queue_size())
        if was_empty:
            self._start_write_request()
        return ret

    def _start_write_request(self):
        if not self.is_connected():
            self.log.debug("_start_write_request: not connected")
            return

        if self._current_request is not None:
            self.log.debug("_start_write_request: request in progress")
            return

        while len(self._queue):
            request, future = self._current_request = self._queue.pop(False) # FIFO order
            self.queue_size_changed.emit(len(self._queue))

            if future.set_running_or_notify_cancel():
                break

        if future.cancelled():
            self._current_request = None
            return

        data = request.serialize()
        data = struct.pack('!H', len(data)) + data # prepend message size
        self.log.debug("_start_write_request: writing %s (len=%d)", request, len(data))
        if self._socket.write(data) == -1:
            future.set_exception(util.SocketError(self._socket.error(), self._socket.errorString()))
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
                self.disconnect()
                return

            self._read_size = 0
            self.message_received.emit(message)

            if message.is_response() or message.is_error():
                request, future = self._current_request

                if message.is_error():
                    future.set_exception(protocol.MessageError(
                        message=message, request=request))

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

    def _socket_disconnected(self):
        self._reset_state(util.Disconnected())
        self.disconnected.emit()

    def _socket_error(self, socket_error):
        error = util.SocketError(socket_error, self._socket.errorString())
        self._reset_state(error)
        self.socket_error.emit(error)
        self.disconnected.emit()

    def _reset_state(self, exception_object=RuntimeError()):
        if self._current_request is not None:
            self.log.debug("_reset_state: aborting current request")
            request, future = self._current_request
            future.set_exception(exception_object)
            self._current_request = None

        self._read_size = 0

        if self.get_queue_size() > 0:
            self.log.debug("_reset_state: aborting %d requests", self.get_queue_size())

            while self.get_queue_size() > 0:
                request, future = self._queue.pop(False)
                future.set_exception(exception_object)

    def get_host(self):
        return self._socket.peerName()

    def get_port(self):
        return self._socket.peerPort()

    host = pyqtProperty(str, get_host)
    port = pyqtProperty(int, get_port)

