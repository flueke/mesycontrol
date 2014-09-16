#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal, pyqtProperty

import protocol
import server_process
import tcp_client
import util

class ConnectionError(Exception):
    pass

class AbstractConnection(QtCore.QObject):
    """Abstract MRC connection representation.
    Supports the following operations:
    * connect/disconnect
    * send/receive messages
    * acquire/force/release write access
    * enable/disable silence
    """

    connecting               = pyqtSignal()
    connected                = pyqtSignal()
    disconnected             = pyqtSignal(object)
    connection_error         = pyqtSignal(ConnectionError)

    message_sent             = pyqtSignal(protocol.Message) #: message
    message_received         = pyqtSignal(protocol.Message) #: message
    response_received        = pyqtSignal(protocol.Message, protocol.Message)   #: request, response

    request_sent             = pyqtSignal(object, protocol.Message)                     #: request_id, request
    request_canceled         = pyqtSignal(object, protocol.Message)                     #: request_id, request
    request_completed        = pyqtSignal(object, protocol.Message, protocol.Message)   #: request_id, request, response

    notification_received    = pyqtSignal(protocol.Message)
    error_received           = pyqtSignal(protocol.Message)

    idle                     = pyqtSignal()
    write_queue_size_changed = pyqtSignal(int)  #: new size

    write_access_changed     = pyqtSignal(bool)
    silence_changed          = pyqtSignal(bool)

    def __init__(self, parent=None):
        super(AbstractConnection, self).__init__(parent)
        self._write_access = False
        self._silenced     = False

    def connect(self):
        raise NotImplementedError()

    def disconnect(self):
        raise NotImplementedError()

    def is_connected(self):
        raise NotImplementedError()

    def is_connecting(self):
        raise NotImplementedError()

    def send_message(self, msg, response_handler=None):
        raise NotImplementedError()

    def get_info(self):
        """Returns an info string for this connection."""
        raise NotImplementedError()

    def get_write_queue_size(self):
        raise NotImplementedError()

    def queue_request(self, msg, response_handler=None):
        raise NotImplementedError()

    def cancel_request(self, request_id):
        raise NotImplementedError()

    def cancel_all_requests(self):
        raise NotImplementedError()

    def has_write_access(self):
        return self._write_access

    def set_write_access(self, want_access, force=False, response_handler=None):
        if want_access:
            t = "request_force_write_access" if force else "request_acquire_write_access"
        else:
            t = "request_release_write_access"

        self.send_message(protocol.Message(t), response_handler)

    def is_silenced(self):
        return self._silenced

    def set_silenced(self, silenced, response_handler=None):
        self.send_message(protocol.Message('request_set_silent_mode', bool_value=silenced),
                response_handler)

    def matches_config(self, connection_config):
        """Returns true if this connection and the given connection_config are
        specifying the same hardware."""
        raise NotImplementedError()

    write_access = pyqtProperty(bool, has_write_access, set_write_access,
            notify=write_access_changed)

    silenced     = pyqtProperty(bool, is_silenced, set_silenced,
            notify=silence_changed)

    def _message_received_handler(self, msg):
        """Default receive handler to be called by subclasses.
        Emits notification_received, error_received, etc. depending on
        the message conents.
        """
        if msg.is_notification():
            self.notification_received.emit(msg)
            t = msg.get_type_name()

            if t == 'notify_silent_mode' and self.silenced != msg.bool_value:
                self._silenced = msg.bool_value
                self.silence_changed.emit(self._silenced)
            elif t == 'notify_write_access' and self.write_access != msg.bool_value:
                self._write_access = msg.bool_value
                self.write_access_changed.emit(self._write_access)
        elif msg.is_error():
            self.error_received.emit(msg)

class MesycontrolConnection(AbstractConnection):
    """TCP connection to a mesycontrol server."""
    def __init__(self, host=None, port=None, parent=None):

        super(MesycontrolConnection, self).__init__(parent)

        self.host    = str(host) if host is not None else None
        self.port    = int(port) if port is not None else None

        self._client = tcp_client.TCPClient(self)
        self._client.connecting.connect(self.connecting)
        self._client.connected.connect(self.connected)
        self._client.disconnected.connect(self._on_client_disconnected)
        self._client.socket_error.connect(self._slt_socket_error)

        self._client.message_sent.connect(self.message_sent)
        self._client.message_received.connect(self.message_received)
        self._client.message_received.connect(self._message_received_handler)
        self._client.response_received.connect(self.response_received)

        self._client.request_sent.connect(self.request_sent)
        self._client.request_canceled.connect(self.request_canceled)
        self._client.request_completed.connect(self.request_completed)

        self._client.write_queue_empty.connect(self.idle)
        self._client.write_queue_size_changed.connect(self.write_queue_size_changed)

    def connect(self):
        if None in (self.host, self.port):
            raise RuntimeError("host or port not set")
        self._client.connect(self.host, self.port)

    def disconnect(self):
        self._client.disconnect()

    def is_connected(self):
        return self._client.is_connected()

    def is_connecting(self):
        return self._client.is_connecting()

    def queue_request(self, msg, response_handler=None):
        return self._client.queue_request(msg, response_handler)

    def get_info(self):
        return "mesycontrol://%s:%d" % (self.host, self.port)

    def get_write_queue_size(self):
        return self._client.get_write_queue_size()
    
    def _on_client_disconnected(self):
        self.disconnected.emit(None)

    def _slt_socket_error(self, errc, errstr):
        self.connection_error.emit(ConnectionError(errstr, errc))

    def matches_config(self, connection_config):
        return (connection_config.is_mesycontrol_connection()
                and connection_config.mesycontrol_host == self.host
                and connection_config.mesycontrol_port == self.port)

    def cancel_request(self, request_id):
        return self._client.cancel_request(request_id)

    def cancel_all_requests(self):
        self._client.cancel_all_requests()

class LocalMesycontrolConnection(MesycontrolConnection):
    """Starts and connects to a local mesycontrol server process."""

    #: Delay between server startup and tcp client connection attempt
    connect_delay_ms = 1000

    def __init__(self, server_options={}, parent=None):
        super(LocalMesycontrolConnection, self).__init__(parent)

        self._server = server_process.pool.create_process(
                options=server_options, parent=self)

        self._server.sig_started.connect(self._slt_server_started)
        self._server.sig_finished.connect(self._slt_server_finished)
        self._server.sig_error.connect(self._slt_server_error)

        self.host = self._server.listen_address
        self.port = self._server.listen_port

        self._connect_timer = QtCore.QTimer(self)
        self._connect_timer.setSingleShot(True)
        self._connect_timer.setInterval(LocalMesycontrolConnection.connect_delay_ms)
        self._connect_timer.timeout.connect(self._slt_connect_timer_timeout)

    def get_server(self):
        return self._server

    server = pyqtProperty(object, get_server)

    def connect(self):
        if not self._server.is_running():
            self._server.start()
        elif not self.is_connected():
            super(LocalMesycontrolConnection, self).connect()

    def disconnect(self):
        super(LocalMesycontrolConnection, self).disconnect()
        self._server.stop()

    def get_info(self):
        return self._server.get_info()

    def _slt_server_started(self):
        if self._server.is_running():
            self.host = self._server.listen_address
            self.port = self._server.listen_port
            self._connect_timer.start()

    def _slt_connect_timer_timeout(self):
        if self._server.is_running():
            super(LocalMesycontrolConnection, self).connect()

    def _slt_server_finished(self, exit_status, exit_code, exit_code_string):
        if exit_code != 0:
            self.connection_error.emit(ConnectionError(
                exit_code_string, exit_code, exit_status))

    def _slt_server_error(self, process_error, error_string, exit_code, exit_code_string):
        self.connection_error.emit(ConnectionError(
            exit_code_string, exit_code, error_string, process_error))

    def matches_config(self, connection_config):
        if connection_config.is_serial_connection():
            return self.server.mrc_serial_port == connection_config.serial_device
        elif connection_config.is_tcp_connection():
            return (self.server.mrc_host == connection_config.tcp_host
                    and self.server.mrc_port == connection_config.tcp_port)
        return False

def factory(**kwargs):
    """Connection factory.
    Supported keyword arguments in order of priority:
        - config:
          MRCConnectionConfig instance specifying the details of the
          connection.
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
    config = kwargs.get('config', None)
    url    = kwargs.get('url', None)
    parent = kwargs.get('parent', None)

    if config is not None:
        ret = None
        if config.is_mesycontrol_connection():
            ret = MesycontrolConnection(host=config.get_mesycontrol_host(),
                    port=config.get_mesycontrol_port(), parent=parent)
        elif config.is_local_connection():
            ret = LocalMesycontrolConnection(server_options=config.get_server_options(),
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
            return MesycontrolConnection(host=mesycontrol_host,
                    port=mesycontrol_port, parent=parent)

        elif None not in (serial_device, serial_baud_rate):
            return LocalMesycontrolConnection(
                    server_options={
                        'mrc_serial_port': serial_device,
                        'mrc_baud_rate': serial_baud_rate},
                    parent=parent)
        elif None not in (tcp_host, tcp_port):
            return LocalMesycontrolConnection(
                    server_options={
                        'mrc_host': tcp_host,
                        'mrc_port': tcp_port},
                    parent=parent)
        else:
            raise RuntimeError("Could not create connection from given arguments")
