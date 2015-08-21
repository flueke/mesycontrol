#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import pyqtSignal

from future import Future
from future import progress_forwarder
from tcp_client import MCTCPClient
import proto
import server_process
import util

# FIXME: disconnected signal of MRCConnection emitted multiple times when
# mesycontrol_server is killed

class IsConnecting(Exception):
    pass

class IsConnected(Exception):
    pass

class AbstractConnection(QtCore.QObject):
    connected               = pyqtSignal()          #: connected and ready to send requests
    disconnected            = pyqtSignal()          #: disconnected; not ready to handle requests
    connecting              = pyqtSignal(object)    #: Establishing the connection. The argument is a
                                                    #: Future instance which fullfills once the connection
                                                    #: is established or an error occurs.
    connection_error        = pyqtSignal(object)    #: error object

    request_queued          = pyqtSignal(object, object) #: request, Future
    request_sent            = pyqtSignal(object, object) #: request, Future
    message_received        = pyqtSignal(object)         #: Message
    response_received       = pyqtSignal(object, object, object) #: request, response, Future
    notification_received   = pyqtSignal(object) #: Message
    error_message_received  = pyqtSignal(object) #: Message

    queue_empty             = pyqtSignal()
    queue_size_changed      = pyqtSignal(int)

    # TODO: add write_access, silence

    def __init__(self, parent=None):
        super(AbstractConnection, self).__init__(parent)

    def connect(self):
        raise NotImplementedError()

    def disconnect(self):
        raise NotImplementedError()

    def is_connected(self):
        raise NotImplementedError()

    def is_connecting(self):
        raise NotImplementedError()

    def is_disconnected(self):
        return not self.is_connected() and not self.is_connecting()

    def queue_request(self, request):
        raise NotImplementedError()

    def get_queue_size(self):
        raise NotImplementedError()

    def get_url(self):
        raise NotImplementedError()

    def get_status(self):
        raise NotImplementedError()

    url = property(lambda self: self.get_url())

class MRCConnection(AbstractConnection):
    def __init__(self, host, port, parent=None):
        super(MRCConnection, self).__init__(parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self.host   = host
        self.port   = port
        self.client = MCTCPClient()

        self.client.disconnected.connect(self._on_client_disconnected)
        self.client.socket_error.connect(self._on_client_socket_error)

        self.client.request_queued.connect(self.request_queued)
        self.client.request_sent.connect(self.request_sent)
        self.client.message_received.connect(self.message_received)
        self.client.response_received.connect(self.response_received)
        self.client.notification_received.connect(self.notification_received)
        self.client.notification_received.connect(self._on_client_notification_received)
        self.client.error_received.connect(self.error_message_received)

        self.client.queue_empty.connect(self.queue_empty)
        self.client.queue_size_changed.connect(self.queue_size_changed)

        self._is_connecting = False
        self._is_connected  = False

    def connect(self):
        self.log.debug("connect() is_connecting=%s, is_connected=%s",
                self.is_connecting(), self.is_connected())

        if self.is_connecting():
            raise IsConnecting()

        if self.is_connected():
            raise IsConnected()

        self._is_connecting = True
        ret = self._connecting_future = Future()

        def on_client_connect_done(f):
            #self.log.debug("connect: on_client_connect_done: ret.done()=%s", ret.done())
            if self._connecting_future is not None and f.exception() is not None:
                self._connecting_future.set_exception(f.exception())
            #else:
            #    ret.set_progress_text("Connected to %s:%d" % (self.host, self.port))

        self.client.connect(self.host, self.port).add_done_callback(on_client_connect_done)
        # FIXME: emitting this causes the gui to see it twice
        #self.log.debug("connect: emitting connecting")
        #self.connecting.emit(ret)
        return ret

    def _on_client_notification_received(self, msg):
        if self.is_connecting() and msg.type == proto.Message.NOTIFY_MRC_STATUS:
            if msg.mrc_status.status == proto.MRCStatus.RUNNING:
                self._is_connecting = False
                self._is_connected  = True
                self._connecting_future.set_result(True)
                self._connecting_future = None
                self.connected.emit()
                self.log.debug("%s: connected & running", self.url)
            else:
                self._connecting_future.set_progress_text("MRC status: %s" %
                        proto.Message.Type.Name(msg.type));
                        #(MRCStatus.by_code[msg.status]['description'],))

    def _on_client_disconnected(self):
        self.log.debug("_on_client_disconnected: connecting_future=%s", self._connecting_future)
        self._is_connected = False
        self._is_connecting = False
        if self._connecting_future is not None:
            self._connecting_future.set_exception(RuntimeError("Socket disconnected"))
            self._connecting_future = None
        self.disconnected.emit()

    def _on_client_socket_error(self, error):
        self.log.debug("_on_client_socket_error: error=%s, connecting_future=%s", error, self._connecting_future)
        self._is_connected = False
        self._is_connecting = False
        if self._connecting_future is not None:
            self._connecting_future.set_exception(error)
            self._connecting_future = None
        self.connection_error.emit(error)

    def disconnect(self):
        self.log.debug("disconnect")
        return self.client.disconnect()

    def is_connected(self):
        return self._is_connected

    def is_connecting(self):
        return self._is_connecting

    def queue_request(self, request):
        return self.client.queue_request(request)

    def get_queue_size(self):
        return self.client.get_queue_size()

    def get_url(self):
        return util.build_connection_url(mc_host=self.host, mc_port=self.port)

class LocalMRCConnection(AbstractConnection):
    connect_delay_ms = 1000 #: delay between server startup and connection attempt

    def __init__(self, server_options=dict(), parent=None):
        super(LocalMRCConnection, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        #self.server = server_process.ServerProcess(**server_options)
        self.server = server_process.pool.create_process(server_options)
        self.connection = MRCConnection(self.server.listen_address, self.server.listen_port)

        self.connection.connected.connect(self.connected)
        self.connection.disconnected.connect(self.disconnected)
        self.connection.connection_error.connect(self.connection_error)
        self.connection.request_queued.connect(self.request_queued)
        self.connection.request_sent.connect(self.request_sent)
        self.connection.message_received.connect(self.message_received)
        self.connection.notification_received.connect(self.notification_received)
        self.connection.error_message_received.connect(self.error_message_received)
        self.connection.queue_empty.connect(self.queue_empty)
        self.connection.queue_size_changed.connect(self.queue_size_changed)

        self._is_connecting = False
        self._is_connected  = False

    def connect(self):
        # Start server, wait for connect_delay_ms, connect to server, done
        ret = Future()

        def on_connection_connected(f):
            try:
                self._is_connecting = False
                ret.set_result(f.result())
                self._is_connected  = True
                self.log.debug("Connected to %s", self.url)

            except Exception as e:
                self.log.error("connect result: %s, f=%s, ret=%s", e, f, ret)
                ret.set_exception(e)

        def on_connect_timer_expired():
            self.connection.host = self.server.listen_address
            self.connection.port = self.server.listen_port
            f = self.connection.connect().add_done_callback(on_connection_connected)
            progress_forwarder(f, ret)

        def on_server_started(f):
            if f.exception() is None:
                self._connect_timer = QtCore.QTimer()
                self._connect_timer.setSingleShot(True)
                self._connect_timer.setInterval(LocalMRCConnection.connect_delay_ms)
                self._connect_timer.timeout.connect(on_connect_timer_expired)
                self._connect_timer.start()
            else:
                self._is_connecting = False
                ret.set_exception(f.exception())
                self.connection_error.emit(f.exception())

        self._is_connected  = False
        self._is_connecting = True
        f = self.server.start().add_done_callback(on_server_started)
        progress_forwarder(f, ret)

        return ret

    def disconnect(self):
        self.log.debug("disconnect")

        ret = Future()

        def on_server_stopped(f):
            self.log.debug("disconnect: on_server_stopped")
            try:
                ret.set_result(f.result())
            except Exception as e:
                ret.set_exception(e)

        def on_connection_disconnected(f):
            self.log.debug("disconnect: on_connection_disconnected")
            self._is_connected = False
            self._is_connecting = False
            if self.server.is_running():
                self.server.stop().add_done_callback(on_server_stopped)
            else:
                ret.set_result(True)

        self.connection.disconnect().add_done_callback(on_connection_disconnected)

        return ret

    def is_connected(self):
        return self._is_connected

    def is_connecting(self):
        return self._is_connecting

    def queue_request(self, request):
        return self.connection.queue_request(request)

    def get_queue_size(self):
        return self.connection.get_queue_size()

    def get_url(self):
        d = dict(serial_port=self.server.serial_port, baud_rate=self.server.baud_rate,
                host=self.server.tcp_host, port=self.server.tcp_port)

        return util.build_connection_url(**d)

def factory(**kwargs):
    """Connection factory.
    Supported keyword arguments in order of priority:
        - config:
          MRCConnectionConfig instance specifying the details of the connection.
        - url:
          A string that is passed to util.parse_connection_url(). The resulting
          dictionary will then be used to create the connection.
        - mc_host, mc_port:
          Creates a MRCConnection to the given host and port.
        - serial_port, baud_rate:
          Creates a LocalMRCConnection using the given serial port and
          baud rate.
        - host, port:
          Creates a LocalMRCConnection connecting to the MRC on the
          given host and port.

    Additionally 'parent' may specify a parent QObject for the resulting
    connection.
    """
    config  = kwargs.get('config', None)
    url     = kwargs.get('url', None)
    parent  = kwargs.get('parent', None)

    if config is not None:
        ret = None
        if config.is_mesycontrol_connection():
            ret = MRCConnection(host=config.get_mesycontrol_host(),
                    port=config.get_mesycontrol_port(), parent=parent)
        elif config.is_local_connection():
            ret = LocalMRCConnection(server_options=config.get_server_options(),
                    parent=parent)
        else:
            raise RuntimeError("Could not create connection from %s" % str(config))

        return ret

    elif url is not None:
        return factory(**util.parse_connection_url(url))
    else:
        mc_host     = kwargs.get('mc_host', None)
        mc_port     = kwargs.get('mc_port', None)
        serial_port = kwargs.get('serial_port', None)
        baud_rate   = kwargs.get('baud_rate', None)
        tcp_host    = kwargs.get('host', None)
        tcp_port    = kwargs.get('port', None)

        if None not in (mc_host, mc_port):
            return MRCConnection(host=mc_host, port=mc_port, parent=parent)

        elif None not in (serial_port, baud_rate):
            return LocalMRCConnection(
                    server_options={
                        'serial_port': serial_port,
                        'baud_rate': baud_rate},
                    parent=parent)
        elif None not in (tcp_host, tcp_port):
            return LocalMRCConnection(
                    server_options={
                        'tcp_host': tcp_host,
                        'tcp_port': tcp_port},
                    parent=parent)
        else:
            raise RuntimeError("Could not create connection from given arguments")
