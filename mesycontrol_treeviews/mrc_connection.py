#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import collections
import struct
from qt import QtCore
from qt import QtNetwork
from qt import pyqtProperty
from qt import pyqtSignal

import protocol
import util
from future import Future

class SocketError(Exception):
    def __init__(self, error_code, error_string):
        self.error_code   = error_code
        self.error_string = error_string

    def __str__(self):
        return self.error_string

RequestResult = collections.namedtuple("RequestResult", "request response")

class MCTCPClient(QtCore.QObject):
    connected           = pyqtSignal()
    disconnected        = pyqtSignal()
    connecting          = pyqtSignal(str, int)
    socket_error        = pyqtSignal(int, str) #: error code, error message

    request_queued      = pyqtSignal(object, object) #: request, Future
    request_sent        = pyqtSignal(object, object) #: request, Future
    message_received    = pyqtSignal(object)         #: Message
    response_received   = pyqtSignal(object, object, object) #: request, response, Future
    queue_empty         = pyqtSignal()

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
            def socket_connected():
                ret.set_result(True)

            def socket_error(socket_error):
                ret.set_exception(SocketError(socket_error, self._socket.errorString()))

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

        def socket_disconnected():
            self._reset_state()
            ret.set_result(True)

        def socket_error(socket_error):
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
        return not self.is_connecting() and self.get_queue_size() == 0

    def get_queue_size(self):
        return len(self._queue)

    def queue_request(self, request):
        """Adds the given request to the outgoing queue. Returns a Future that
        fullfills once a response is received or an error occurs."""
        was_empty = self.get_queue_size() == 0
        ret = Future()
        self._queue.add((request, ret))
        self.request_queued.emit(request, ret)
        if was_empty:
            self._start_write_request()
        return ret

    def _start_write_request(self):
        if not self.is_connected() or self._current_request is not None:
            self.log.debug("_start_write_request: not connected or request in progress")
            return

        request, future = self._current_request = self._queue.pop(False) # FIFO order
        data = request.serialize()
        data = struct.pack('!H', len(data)) + data # prepend message size
        self.log.debug("_start_write_request: writing %s (len=%d)", request, len(data))
        if self._socket.write(data) == -1:
            future.set_exception(SocketError(self._socket.error(), self._socket.errorString()))
        else:
            def bytes_written():
                self.log.debug("_start_write_request: request %s sent", request)
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

            if message.is_response():
                request, future = self._current_request
                future.set_result(RequestResult(request, message))
                self.response_received.emit(request, message, future)
                self._current_request = None
                if self.get_queue_size() > 0:
                    self._start_write_request()
                else:
                    self.queue_empty.emit()

            if self._socket.bytesAvailable() >= 2:
                # Handle additional available data.
                self._socket_readyRead()

    def _socket_error(self, socket_error):
        self.socket_error.emit(socket_error, self._socket.errorString())
        self.disconnected.emit()

    def get_host(self):
        return self._socket.peerName()

    def get_port(self):
        return self._socket.peerPort()

    host = pyqtProperty(str, get_host)
    port = pyqtProperty(int, get_port)

class MRCConnection(QtCore.QObject):
    def __init__(self, host, port, parent=None):
        super(MRCConnection, self).__init__(parent)
        self.client = MCTCPClient()
        self.host = host
        self.port = port

    def connect(self):
        return self.client.connect(self.host, self.port)

    def disconnect(self):
        return self.client.disconnect()

class LocalMRCConnection:
    def __init__(self, server_options=dict(), parent=None):
        self.server = ServerProcess(*server_options)
        self.client = MCTCPClient()

    def connect(self):
        ret = Future()

        def on_connected(f):
            try:
                ret.set_result(f.result())
            except Exception as e:
                ret.set_exception(e)

        def on_server_started(f):
            if f.exception() is None:
                g = self.client.connect(self.server.listen_address, self.server.listen_port)
                g.add_done_callback(on_connected)
            else:
                ret.set_exception(f.exception())

        self.server.start().add_done_callback(on_server_started)

        return ret

    def disconnect(self):
        ret = Future()

        def set_result(f):
            try:
                ret.set_result(f.result())
            except Exception as e:
                ret.set_exception(e)

        def stop_server(f):
            self.server.stop().add_done_callback(set_result)

        self.client.disconnect().add_done_callback(stop_server)

        return ret

class ServerError(Exception):
    pass

class ServerIsRunning(ServerError):
    pass

class ServerIsStopped(ServerError):
    pass

QProcess = QtCore.QProcess

class ServerProcess(QtCore.QObject):
    started  = pyqtSignal()
    error    = pyqtSignal(QProcess.ProcessError, str, int, str)
    finished = pyqtSignal(QProcess.ExitStatus, int, str)
    output   = pyqtSignal(str)

    exit_codes = {
            0:   "exit_success",
            1:   "exit_options_error",
            2:   "exit_address_in_use",
            3:   "exit_address_not_available",
            4:   "exit_permission_denied",
            5:   "exit_bad_listen_address",
            127: "exit_unknown_error"
            }

    def __init__(self, binary='mesycontrol_server', listen_address='127.0.0.1', listen_port=23000,
            serial_port=None, baud_rate=0, tcp_host=None, tcp_port=4001, verbosity=3, parent=None):

        super(ServerProcess, self).__init__(parent)

        self.binary = binary
        self.listen_address = listen_address
        self.listen_port = listen_port
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.verbosity = verbosity

        self.process = QProcess()
        self.process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.process.started.connect(self.started)
        self.process.error.connect(self._error)
        self.process.finished.connect(self._finished)
        self.process.readyReadStandardOutput.connect(self._stdout)

    def start(self):
        ret = Future()

        try:
            if self.process.state() != QtCore.QProcess.NotRunning:
                raise ServerIsRunning()

            args = self._prepare_args()
            program = util.which(self.binary)

            if program is None:
                raise RuntimeError("Could not find server binary '%s'" % self.binary)

            # cmd_line = "%s %s" % (program, " ".join(args))

            def on_started():
                ret.set_result(True)

            def on_error(error):
                ret.set_exception(ServerError(error))

            self.process.started.connect(on_started)
            self.process.error.connect(on_error)

            self.process.start(program, args, QtCore.QIODevice.ReadOnly)

        except Exception as e:
            ret.set_exception(e)

        return ret

    def stop(self, kill=False):
        ret = Future()

        if self.process.state() != QtCore.QProcess.NotRunning:
            def on_finished(code, status):
                ret.set_result(True)

            self.process.finished.connect(on_finished)
            if not kill:
                self.process.terminate()
            else:
                self.process.kill()
        else:
            ret.set_exception(ServerIsStopped())
        return ret

    def kill(self):
        return self.stop(True)

    def is_starting(self):
        return self.process.state() == QtCore.QProcess.Starting

    def is_running(self):
        return self.process.state() == QtCore.QProcess.Running

    def exit_code(self):
        code = self.process.exitCode()
        return (code, ServerProcess.exit_code_string(code))

    @staticmethod
    def exit_code_string(code):
        return ServerProcess.exit_codes.get(code, "exit_unknown_error")

    def _prepare_args(self):
        args = list()

        if self.verbosity != 0:
            # verbose/quiet flags (-vvv / -qqq)
            verb_flag = 'v' if self.verbosity > 0 else 'q'
            verb_args = '-' + verb_flag * abs(self.verbosity)
            args.append(verb_args)

        args.extend(['--listen-address', self.listen_address])
        args.extend(['--listen-port', str(self.listen_port)])

        if self.serial_port is not None:
            args.extend(['--mrc-serial-port', self.serial_port])
            args.extend(['--mrc-baud-rate', str(self.baud_rate)])
        elif self.tcp_host is not None:
            args.extend(['--mrc-host', self.tcp_host])
            args.extend(['--mrc-port', str(self.tcp_port)])
        else:
            raise RuntimeError("Neither serial_port nor tcp_host given.")

        return args

    def _error(self, error):
        self.error.emit(error, self.process.errorString(), ServerProcess.exit_code_string(error))

    def _finished(self, code, status):
        self.finished.emit(status, code, ServerProcess.get_exit_code_string(code))

if __name__ == "__main__":
    from qt import QtGui
    import logging
    import pyqtgraph as pg
    import pyqtgraph.console
    import signal
    import sys

    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    def signal_handler(signum, frame):
        QtGui.QApplication.quit()

    app = QtGui.QApplication(sys.argv)
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)
    signal.signal(signal.SIGINT, signal_handler)

    h, p = (str(sys.argv[1]), int(sys.argv[2]))
    c = MCTCPClient()
    def connected(f):
        if f.result():
            print "Connected to %s:%d" % (c.host, c.port)
            m = protocol.Message('request_scanbus', bus=0)
            f = c.queue_request(m)
            def request_done(f):
                print f.result()
            f.add_done_callback(request_done)

    c.connect(h, p).add_done_callback(connected)


    console = pg.console.ConsoleWidget(namespace=locals())
    console.show()

    sys.exit(app.exec_())
