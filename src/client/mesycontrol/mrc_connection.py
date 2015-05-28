#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import pyqtSignal

from future import Future
from protocol import MRCStatus
from tcp_client import MCTCPClient
import server_process
import util

class IsConnecting(Exception):
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
    error_received          = pyqtSignal(object) #: Message

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

    def queue_request(self, request):
        raise NotImplementedError()

    def get_url(self):
        raise NotImplementedError()

    def get_status(self):
        raise NotImplementedError()

class MRCConnection(AbstractConnection):
    def __init__(self, host, port, parent=None):
        super(MRCConnection, self).__init__(parent)
        self.host   = host
        self.port   = port
        self.client = MCTCPClient()

        #self.client.connected.connect(self.connected)
        self.client.disconnected.connect(self.disconnected)
        #self.client.connecting.connect(self.connecting)
        self.client.socket_error.connect(self.connection_error)

        self.client.request_queued.connect(self.request_queued)
        self.client.request_sent.connect(self.request_sent)
        self.client.message_received.connect(self.message_received)
        self.client.response_received.connect(self.response_received)
        self.client.notification_received.connect(self.notification_received)
        self.client.error_received.connect(self.error_received)

        self.client.queue_empty.connect(self.queue_empty)
        self.client.queue_size_changed.connect(self.queue_size_changed)

    # FIXME: leftoff here. how to do this properly?
# how to handle protocol level MRC status:
# client = MCTCPClient()
# client.connect()
# wait for connected (socket level)
# wait for status notification (this is the first message the server sends)
# if status == running:
#  self.connected.emit() and self.is_connected() == true
# continue handling status notifications

# It would be nice to keep knowledge about MRCStatus inside protocol.py and
# this file. Clients should get an object which should yield a human readable
# status description when converted to string.
# => connect() returns a Future which will get progress_text updates during the
# connection attempt. This way the LocalMRCConnection can issue updates
# concerning server startup, the MRCConnection issues updates about the socket
# status.
# The connecting() signal has the Future returned by connect() as an argument.
# This way observer gain access to the Future and can react to progress_text
# updates.
# Calling connect() while a connection attempt is in progress should raise an
# Exception.
# Drawback: can't send anything to the server it has established the MRC
# connection. No status requests, nothing. It's not functional until the server
# side MRC connection is established and ready.

# New problem case:
# The connection was established on both socket and protocol level. Now the
# server loses MRC connectivity and thus sends out an mrc_status change
# notification.
# This means this connection is not ready anymore and can't be used. But it's
# not completely disconnected either and just waiting until the server
# re-establishes the MRC connection might be enough. Also there's no user
# action available to trigger a protocol level reconnect.

# What I want:
# - A clear indication of the state of a connection
# - Notifications when the state changes
# - Error messages for the user
# - 

    def connect(self):
        if self.is_connecting():
            raise IsConnecting()

        ret = Future()

        def on_client_connect_done(f):
            if f.exception() is not None:
                ret.set_exception(f.exception())
            else:
                ret.set_progress_text("Connected to %s:%d" % (self.host, self.port))

        def on_client_notification_received(msg):
            if msg.get_type_name() != 'mrc_status':
                return

            if msg.status == MRCStatus.RUNNING:
                self.client.notification_received.disconnect(on_client_notification_received)
                ret.set_progress_text("Ready")
                ret.set_result(True)
            else:
                ret.set_progress_text("MRC: %s" % (MRCStatus.by_code[msg.status].description))

        self.client.notification_received.connect(on_client_notification_received)
        self.client.connect(self.host, self.port).add_done_callback(on_client_connect_done)
        self.connecting.emit(ret)
        return ret

    def connect(self):
        ret = Future()

        def on_client_connect_done(f):
            if f.exception() is not None:
                ret.set_exception(f.exception())

        def on_client_notification_received(msg):
            if (msg.get_type_name() == 'mrc_status' and
                    msg.status == MRCStatus.RUNNING):
                self.client.notification_received.disconnect(on_client_notification_received)
                ret.set_result(True)

        self.client.notification_received.connect(on_client_notification_received)
        self.client.connect(self.host, self.port).add_done_callback(on_client_connect_done)

        return ret

    def disconnect(self):
        return self.client.disconnect()

    def is_connected(self):
        #return self.client.is_connected()

    def queue_request(self, request):
        return self.client.queue_request(request)

    def get_url(self):
        return util.build_connection_url(mc_host=self.host, mc_port=self.port)

class LocalMRCConnection(AbstractConnection):
    connect_delay_ms = 1000 #: delay between server startup and connection attempt

    def __init__(self, server_options=dict(), parent=None):
        super(LocalMRCConnection, self).__init__(parent)
        self.server = server_process.pool.create_process(server_options)
        self.client = MCTCPClient()

        self.client.connected.connect(self.connected)
        self.client.disconnected.connect(self.disconnected)
        self.client.connecting.connect(self.connecting)
        self.client.socket_error.connect(self.connection_error)

        self.client.request_queued.connect(self.request_queued)
        self.client.request_sent.connect(self.request_sent)
        self.client.message_received.connect(self.message_received)
        self.client.response_received.connect(self.response_received)
        self.client.notification_received.connect(self.notification_received)
        self.client.error_received.connect(self.error_received)

        self.client.queue_empty.connect(self.queue_empty)
        self.client.queue_size_changed.connect(self.queue_size_changed)

    def connect(self):
        ret = Future()

        def on_connected(f):
            try:
                ret.set_result(f.result())
            except Exception as e:
                ret.set_exception(e)

        def on_connect_timer_expired():
            g = self.client.connect(self.server.listen_address, self.server.listen_port)
            g.add_done_callback(on_connected)

        def on_server_started(f):
            if f.exception() is None:
                self._connect_timer = QtCore.QTimer()
                self._connect_timer.setSingleShot(True)
                self._connect_timer.setInterval(LocalMRCConnection.connect_delay_ms)
                self._connect_timer.timeout.connect(on_connect_timer_expired)
                self._connect_timer.start()
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

    def is_connected(self):
        return self.client.is_connected()

    def is_disconnected(self):
        return self.client.is_disconnected()

    def queue_request(self, request):
        return self.client.queue_request(request)

    def get_url(self):
        return util.build_connection_url(
                serial_port=self.server.serial_port, baud_rate=self.server.baud_rate
                host=self.server.tcp_host, port=self.server.tcp_port)
        #if self.server.serial_port:
        #    return "serial://%s:%d" % (self.server.serial_port, self.server.baud_rate)
        #else:
        #    return "tcp://%s:%d" % (self.server.tcp_host, self.server.tcp_port)

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
