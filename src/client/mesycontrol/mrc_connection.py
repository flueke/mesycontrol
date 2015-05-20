#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import pyqtSignal

from future import Future
from tcp_client import MCTCPClient
import server_process
import util

class AbstractConnection(QtCore.QObject):
    connected               = pyqtSignal()
    disconnected            = pyqtSignal()
    connecting              = pyqtSignal()
    connection_error        = pyqtSignal(object)   #: error object

    request_queued          = pyqtSignal(object, object) #: request, Future
    request_sent            = pyqtSignal(object, object) #: request, Future
    message_received        = pyqtSignal(object)         #: Message
    response_received       = pyqtSignal(object, object, object) #: request, response, Future
    notification_received   = pyqtSignal(object) #: Message
    error_received          = pyqtSignal(object) #: Message

    queue_empty             = pyqtSignal()
    queue_size_changed      = pyqtSignal(int)

    # TODO: add write_access, silence, mrc status

    def __init__(self, parent=None):
        super(AbstractConnection, self).__init__(parent)

    def connect(self):
        raise NotImplementedError()

    def disconnect(self):
        raise NotImplementedError()

    def is_connected(self):
        raise NotImplementedError()

    def queue_request(self, request):
        raise NotImplementedError()

class MRCConnection(AbstractConnection):
    def __init__(self, host, port, parent=None):
        super(MRCConnection, self).__init__(parent)
        self.host   = host
        self.port   = port
        self.client = MCTCPClient()

        self.client.connected.connect(self.connected)
        self.client.disconnected.connect(self.disconnected)
        self.client.connecting.connect(self.connecting)
        self.client.socket_error.connect(self.connection_error)

        self.client.request_queued.connect(self.request_queued)
        self.client.request_sent.connect(self.request_sent)
        self.client.message_received.connect(self.message_received)
        self.client.response_received.connect(self.response_received)
        self.client.notification_received(self.notification_received)
        self.client.error_received(self.error_received)

        self.client.queue_empty.connect(self.queue_empty)
        self.client.queue_size_changed(self.queue_size_changed)

    def connect(self):
        return self.client.connect(self.host, self.port)

    def disconnect(self):
        return self.client.disconnect()

    def is_connected(self):
        return self.client.is_connected()

    def queue_request(self, request):
        return self.client.queue_request(request)

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
        self.client.notification_received(self.notification_received)
        self.client.error_received(self.error_received)

        self.client.queue_empty.connect(self.queue_empty)
        self.client.queue_size_changed(self.queue_size_changed)

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

    def queue_request(self, request):
        return self.client.queue_request(request)

def factory(**kwargs):
    """Connection factory.
    Supported keyword arguments in order of priority:
        - config:
          MRCConnectionConfig instance specifying the details of the connection.
        - url:
          A string that is passed to util.parse_connection_url(). The resulting
          dictionary will then be used to create the connection.
        - mesycontrol_host, mesycontrol_port:
          Creates a MesycontrolConnection to the given host and port.
        - serial_port, baud_rate:
          Creates a LocalMesycontrolConnection using the given serial port and
          baud rate.
        - host, port:
          Creates a LocalMesycontrolConnection connecting to the MRC on the
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
        mesycontrol_host = kwargs.get('mesycontrol_host', None)
        mesycontrol_port = kwargs.get('mesycontrol_port', None)
        serial_device    = kwargs.get('serial_port', None)
        serial_baud_rate = kwargs.get('baud_rate', None)
        tcp_host         = kwargs.get('host', None)
        tcp_port         = kwargs.get('port', None)

        if None not in (mesycontrol_host, mesycontrol_port):
            return MRCConnection(host=mesycontrol_host,
                    port=mesycontrol_port, parent=parent)

        elif None not in (serial_device, serial_baud_rate):
            return LocalMRCConnection(
                    server_options={
                        'mrc_serial_port': serial_device,
                        'mrc_baud_rate': serial_baud_rate},
                    parent=parent)
        elif None not in (tcp_host, tcp_port):
            return LocalMRCConnection(
                    server_options={
                        'mrc_host': tcp_host,
                        'mrc_port': tcp_port},
                    parent=parent)
        else:
            raise RuntimeError("Could not create connection from given arguments")
