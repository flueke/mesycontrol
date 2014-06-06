#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal, pyqtProperty
from protocol import Message
from mrc_model import MRCModel
from util import parse_connection_url
import tcp_client
import server_process

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

    sig_connecting              = pyqtSignal()
    sig_connected               = pyqtSignal()
    sig_disconnected            = pyqtSignal()
    sig_connection_error        = pyqtSignal(ConnectionError)
    sig_idle                    = pyqtSignal()
    sig_message_sent            = pyqtSignal(Message)
    sig_message_received        = pyqtSignal(Message)
    sig_response_received       = pyqtSignal(Message, Message)
    sig_notification_received   = pyqtSignal(Message)
    sig_error_received          = pyqtSignal(Message)
    sig_write_access_changed    = pyqtSignal(bool)
    sig_silence_changed         = pyqtSignal(bool)

    def __init__(self, parent=None):
        super(AbstractConnection, self).__init__(parent)
        self._write_access = False
        self._silenced     = False
        self.mrc_model     = MRCModel(self, self)

    def connect(self):
        raise NotImplemented()

    def disconnect(self):
        raise NotImplemented()

    def is_connected(self):
        raise NotImplemented()

    def send_message(self, msg, response_handler=None):
        raise NotImplemented()

    def get_info(self):
        """Returns an info string for this connection."""
        raise NotImplemented()

    def get_tx_queue_size(self):
        raise NotImplemented()

    def has_write_access(self):
        return self._write_access

    def set_write_access(self, want_access, force=False, response_handler=None):
        if want_access:
            t = "request_force_write_access" if force else "request_acquire_write_access"
        else:
            t = "request_release_write_access"

        self.send_message(Message(t), response_handler)

    def is_silenced(self):
        return self._silenced

    def set_silenced(self, silenced, response_handler=None):
        self.send_message(Message('request_set_silent_mode', bool_value=silenced),
                response_handler)

    write_access = pyqtProperty(bool, has_write_access, set_write_access,
            notify=sig_write_access_changed)

    silenced = pyqtProperty(bool, is_silenced, set_silenced,
            notify=sig_silence_changed)

    def _message_received_handler(self, msg):
        """Default receive handler to be called by subclasses.
        Emits sig_notification_received, sig_error_received, etc. depending on
        the message conents.
        Note: request/response matching is not handled by this method.
        Subclasses have to implement it themselves.
        """
        if msg.is_notification():
            self.sig_notification_received.emit(msg)
            t = msg.get_type_name()

            if t == 'notify_silent_mode' and self.silenced != msg.bool_value:
                self._silenced = msg.bool_value
                self.sig_silence_changed.emit(self._silenced)
            elif t == 'notify_write_access' and self.write_access != msg.bool_value:
                self._write_access = msg.bool_value
                self.sig_write_access_changed.emit(self._write_access)

        elif msg.is_error():
            self.sig_error_received.emit(msg)

class MesycontrolConnection(AbstractConnection):
    """TCP connection to a mesycontrol server."""
    def __init__(self, host=None, port=None, parent=None):

        super(MesycontrolConnection, self).__init__(parent)

        self.host    = str(host) if host is not None else None
        self.port    = int(port) if port is not None else None

        self._client = tcp_client.TCPClient(self)
        self._client.sig_connecting.connect(self.sig_connecting)
        self._client.sig_connected.connect(self.sig_connected)
        self._client.sig_disconnected.connect(self.sig_disconnected)
        self._client.sig_socket_error.connect(self._slt_socket_error)
        self._client.sig_message_sent.connect(self.sig_message_sent)
        self._client.sig_message_received.connect(self.sig_message_received)
        self._client.sig_message_received.connect(self._message_received_handler)
        self._client.sig_response_received.connect(self.sig_response_received)
        self._client.sig_tx_queue_empty.connect(self.sig_idle)

    def connect(self):
        if None in (self.host, self.port):
            raise RuntimeError("host or port not set")
        self._client.connect(self.host, self.port)

    def disconnect(self):
        self._client.disconnect()

    def is_connected(self):
        return self._client.is_connected()

    def send_message(self, msg, response_handler=None):
        self._client.send_message(msg, response_handler)

    def get_info(self):
        return "mesycontrol://%s:%d" % (self.host, self.port)

    def get_tx_queue_size(self):
        return self._client.get_write_queue_size()

    def _slt_socket_error(self, errc, errstr):
        self.sig_connection_error.emit(ConnectionError(errstr, errc))

class LocalMesycontrolConnection(MesycontrolConnection):
    """Starts and uses a local mesycontrol server process."""

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
            self.sig_connection_error.emit(ConnectionError(
                exit_code_string, exit_code, exit_status))

    def _slt_server_error(self, process_error, error_string, exit_code, exit_code_string):
        self.sig_connection_error.emit(ConnectionError(
            exit_code_string, exit_code, error_string, process_error))

# TODO: add VirtualConnection

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
        if config.is_mesycontrol_connection():
            return MesycontrolConnection(host=config.get_mesycontrol_host(),
                    port=config.get_mesycontrol_port(), parent=parent)
        elif config.is_local_connection():
            return LocalMesycontrolConnection(server_options=config.get_server_options(),
                    parent=parent)
        else:
            raise RuntimeError("Could not create connection from %s" % str(config))
    elif url is not None:
        return factory(**parse_connection_url(url))
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
