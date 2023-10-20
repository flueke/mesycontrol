#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2021 mesytec GmbH & Co. KG <info@mesytec.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

__author__ = 'Florian Lüke'
__email__  = 'f.lueke@mesytec.com'

from mesycontrol.qt import Property
from mesycontrol.qt import Signal
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtNetwork
import collections
import struct

from mesycontrol.future import Future
from google.protobuf import message as proto_message
import mesycontrol.proto as proto
import mesycontrol.util as util

RequestResult = collections.namedtuple("RequestResult", "request response")

class MCTCPClient(QtCore.QObject):
    """Mesycontrol TCP client"""

    connected               = Signal()
    disconnected            = Signal()
    connecting              = Signal(str, int)
    socket_error            = Signal(object)   #: instance of SocketError

    request_queued          = Signal(object, object) #: request, Future
    request_sent            = Signal(object, object) #: request, Future
    message_received        = Signal(object)         #: Message
    response_received       = Signal(object, object, object) #: request, response, Future
    notification_received   = Signal(object) #: Message
    error_received          = Signal(object) #: Message

    queue_empty             = Signal()
    queue_size_changed      = Signal(int)

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

    def connectClient(self, host, port):
        """Connect to the given host and port.
        Returns a Future that fullfills once the connection has been
        established or an error occurs.
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
                #self.log.error("Error connecting to %s:%d: %s", host, port,
                #        self._socket.errorString())
                dc()
                ret.set_exception(util.SocketError(socket_error, self._socket.errorString()))
                #self.log.error("%s", ret.exception())

            self._reset_state()
            self._socket.connected.connect(socket_connected)
            self._socket.error.connect(socket_error)
            self._socket.connectToHost(host, port)
            self.log.debug("connect: emitting connecting")
            self.connecting.emit(host, port)

        if self.is_connected() or self.is_connecting():
            self.disconnectClient().add_done_callback(do_connect)
        else:
            do_connect()

        return ret

    def disconnectClient(self):
        """Disconnect. Returns a Future that fullfills once the connection has
        been disconnected or an error occurs."""

        self.log.debug("disconnectClient()")

        if not self.is_disconnected():
            self._socket.disconnectFromHost()

        return Future().set_result(True)

        #host, port = self.host, self.port

        #def dc():
        #    self._socket.disconnected.disconnect(socket_disconnected)
        #    self._socket.error.disconnect(socket_error)

        #def socket_disconnected():
        #    self.log.debug("Disconnected from %s:%d", host, port)
        #    dc()
        #    ret.set_result(True)

        #def socket_error(socket_error):
        #    #self.log.error("Socket error from %s:%d: %s", host, port,
        #    #        self._socket.errorString())
        #    dc()
        #    ret.set_exception(util.SocketError(socket_error, self._socket.errorString()))

        #self._socket.disconnected.connect(socket_disconnected)
        #self._socket.error.connect(socket_error)

        #return ret

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

        if request.ByteSize() == 0:
            raise RuntimeError("request has 0 length; request=%s" % request)

        was_empty = self.get_queue_size() == 0
        hashable_request = request.SerializeToString()
        self._queue.add((hashable_request, ret))
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
            str_request, future = self._queue.pop(False) # FIFO order
            request = proto.Message()
            request.ParseFromString(str_request)
            self._current_request = (request, future)
            self.queue_size_changed.emit(len(self._queue))

            if future.set_running_or_notify_cancel():
                break

        if future.cancelled():
            self._current_request = None
            return

        self.log.debug("_start_write_request: request=%s, str_request=%s, len(str_request)=%d",
                request, str_request, len(str_request));

        data = str_request
        data = struct.pack('!H', len(data)) + data # prepend message size
        self.log.debug("_start_write_request: writing %s (len=%d)", request, len(data))
        if self._socket.write(bytes(data)) == -1:
            future.set_exception(util.SocketError(self._socket.error(),
                self._socket.errorString()))
        else:
            def bytes_written():
                self.log.debug("_start_write_request: request %s sent", request)
                self._socket.bytesWritten.disconnect(bytes_written)
                self.request_sent.emit(request, future)
            self._socket.bytesWritten.connect(bytes_written)

    def _socket_readyRead(self):
        while True:
            # Changed on 231019 to avoid a recursive call to _socket_readyRead.
            if self._read_size <= 0 and self._socket.bytesAvailable() < 2:
                return

            if self._read_size > 0 and self._socket.bytesAvailable() < self._read_size:
                return

            if self._read_size <= 0 and self._socket.bytesAvailable() >= 2:
                # Note: added the bytes() conversion when porting to PySide2.
                # Without it the struct.unpack() call would lead to a segmentation
                # fault.
                data = bytes(self._socket.read(2))
                self._read_size = struct.unpack('!H', data)[0]
                self.log.debug("_socket_readyRead: incoming msg size = %d", self._read_size)

            if self._read_size > 0 and self._socket.bytesAvailable() >= self._read_size:
                message_data = bytes(self._socket.read(self._read_size))
                self.log.debug("_socket_readyRead: read %u bytes from socket, %u bytes left to read",
                            len(message_data), self._socket.bytesAvailable())
                try:
                    message = proto.Message()
                    message.ParseFromString(message_data)
                    self.log.debug("_socket_readyRead: received %s", message.Type.Name(message.type))
                except proto_message.DecodeError as e:
                    self.log.error("Could not deserialize incoming message: %s.", e)
                    self.disconnectClient()
                    return

                self._read_size = 0
                self.message_received.emit(message)

                if proto.is_response(message):
                    request, future = self._current_request

                    if proto.is_error_response(message):
                        future.set_exception(proto.MessageError(
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

                elif proto.is_notification(message):
                    self.notification_received.emit(message)

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
            if not future.done():
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

    host = Property(str, get_host)
    port = Property(int, get_port)

if __name__ == "__main__":
    client = MCTCPClient()
    def on_client_disconnected():
        print("on_client_disconnected")
    print(client.disconnected.connect)
    print(client.disconnected.connect(on_client_disconnected))
