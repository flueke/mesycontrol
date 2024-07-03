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

from mesycontrol.qt import QtCore
from mesycontrol.qt import Signal
from mesycontrol.qt import Slot
import errno

from mesycontrol.future import Future
from mesycontrol.future import progress_forwarder
from mesycontrol.tcp_client import MCTCPClient
import mesycontrol.proto as proto
import mesycontrol.server_process as server_process
import mesycontrol.util as util

class IsConnecting(Exception):
    pass

class IsConnected(Exception):
    pass

class AbstractMrcConnection(QtCore.QObject):
    connected               = Signal()          #: connected and ready to send requests
    disconnected            = Signal()          #: disconnected; not ready to handle requests
    connecting              = Signal(object)    #: Establishing the connection. The argument is a
                                                #: Future instance which fullfills once the connection
                                                #: is established or an error occurs.
    connection_error        = Signal(object)    #: error object

    request_queued          = Signal(object, object) #: request, Future
    request_sent            = Signal(object, object) #: request, Future
    message_received        = Signal(object)         #: Message
    response_received       = Signal(object, object, object) #: request, response, Future
    notification_received   = Signal(object) #: Message
    error_message_received  = Signal(object) #: Message

    queue_empty             = Signal()
    queue_size_changed      = Signal(int)

    def __init__(self, parent=None):
        super(AbstractMrcConnection, self).__init__(parent)

    def connectMrc(self):
        raise NotImplementedError()

    def disconnectMrc(self):
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

    url = property(lambda self: self.get_url())

class MRCConnection(AbstractMrcConnection):
    def __init__(self, host, port, parent=None):
        super(MRCConnection, self).__init__(parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self.host   = host
        self.port   = port
        self.client = MCTCPClient()

        self.client.disconnected.connect(self.on_client_disconnected)
        self.client.socket_error.connect(self.on_client_socket_error)

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

    def connectMrc(self):
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

        self.client.connectClient(self.host, self.port).add_done_callback(on_client_connect_done)
        # FIXME: emitting this causes the gui to see it twice
        #self.log.debug("connect: emitting connecting")
        #self.connecting.emit(ret)
        return ret

    def _on_client_notification_received(self, msg):
        if self.is_connecting() and msg.type == proto.Message.NOTIFY_MRC_STATUS:
            SC = proto.MRCStatus.StatusCode
            if msg.mrc_status.code == proto.MRCStatus.RUNNING:
                self._is_connecting = False
                self._is_connected  = True
                self._connecting_future.set_result(True)
                self._connecting_future = None
                self.connected.emit()
                self.log.debug("%s: connected & running", self.url)
            elif (msg.mrc_status.code not in (SC.CONNECTING, SC.INITIALIZING)):
                self._connecting_future.set_progress_text("MRC status: %s%s%s" % (
                        proto.MRCStatus.StatusCode.Name(msg.mrc_status.code),
                        " - " if len(msg.mrc_status.info) else str(),
                        msg.mrc_status.info
                        ))

    @Slot()
    def on_client_disconnected(self):
        self.log.debug("_on_client_disconnected: connecting_future=%s", self._connecting_future)
        self._is_connected = False
        self._is_connecting = False
        if self._connecting_future is not None:
            self._connecting_future.set_exception(RuntimeError("Socket disconnected"))
            self._connecting_future = None
        self.disconnected.emit()

    @Slot(object)
    def on_client_socket_error(self, error):
        self.log.debug("_on_client_socket_error: error=%s, connecting_future=%s", error, self._connecting_future)
        self._is_connected = False
        self._is_connecting = False
        if self._connecting_future is not None:
            self._connecting_future.set_exception(error)
            self._connecting_future = None
        self.connection_error.emit(error)

    def disconnectMrc(self):
        self.log.debug("disconnectMrc")
        return self.client.disconnectClient()

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

class LocalMRCConnection(AbstractMrcConnection):
    connect_delay_ms = 1000 #: delay between server startup and connection attempt

    def __init__(self, server_options=dict(), parent=None):
        super(LocalMRCConnection, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.server = server_process.pool.create_process(server_options)

        self.connection = MRCConnection(self.server.listen_address, self.server.listen_port)
        self.connection.connected.connect(self.connected)
        self.connection.disconnected.connect(self.disconnected)
        self.connection.connection_error.connect(self.connection_error)
        self.connection.request_queued.connect(self.request_queued)
        self.connection.request_sent.connect(self.request_sent)
        self.connection.message_received.connect(self.message_received)
        self.connection.notification_received.connect(self.notification_received)
        self.connection.notification_received.connect(self._on_connection_notification_received)
        self.connection.error_message_received.connect(self.error_message_received)
        self.connection.queue_empty.connect(self.queue_empty)
        self.connection.queue_size_changed.connect(self.queue_size_changed)

        self._connecting_future = None
        self._is_connecting = False
        self._is_connected  = False

    def connectMrc(self):
        if self._connecting_future is not None and not self._connecting_future.done():
            return self._connecting_future

        # Start server, wait for connect_delay_ms, connect to server, done
        self._connecting_future = ret = Future()

        def on_connection_connected(f):
            try:
                self._is_connecting = False
                ret.set_result(f.result())
                self._is_connected  = True
                self._connecting_future = None
                self.log.debug("Connected to %s", self.url)

            except Exception as e:
                #self.log.error("connect result: %s, f=%s, ret=%s", e, f, ret)
                ret.set_exception(e)

        def on_connect_timer_expired():
            self.connection.host = self.server.listen_address
            self.connection.port = self.server.listen_port
            f = self.connection.connectMrc().add_done_callback(on_connection_connected)
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

    def disconnectMrc(self):
        self.log.debug("disconnectMrc")
        ret = Future()

        if self.server.is_running():
            def handle_quit_response(f):
                try:
                    f.result()
                except util.Disconnected:
                    self.log.info(f"disconnectMrc: was already disconnected")
                    pass # Already had lost the connection to the server.
                except Exception as e:
                    self.log.info(f"disconnectMrc: exception from 'Quit' request: {e}")

                def on_server_stopped(stopFuture):
                    self.log.debug(f"disconnectMrc.on_server_stopped {stopFuture}")
                    self._is_connected = False
                    self._is_connecting = False
                    ret.set_result(True)

                def stop_server(disconnectFuture):
                    self.log.debug(f"disconnectMrc.stop_server {disconnectFuture}")
                    self.server.stop().add_done_callback(on_server_stopped)

                self.log.debug(f"disconnecting MRC connection instance {self.connection}")
                self.connection.disconnectMrc().add_done_callback(stop_server)

            req = proto.Message()
            req.type = proto.Message.REQ_QUIT
            self.queue_request(req).add_done_callback(handle_quit_response)
        else:
            ret.set_result(True)

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

    def _on_connection_notification_received(self, msg):
        if (self.is_connecting()
                and msg.type == proto.Message.NOTIFY_MRC_STATUS
                and msg.mrc_status.reason == errno.EACCES
                and self.server.serial_port is not None):
            try:
                import os, pwd, grp
                ser = self.server.serial_port
                fs  = os.stat(ser)
                o   = pwd.getpwuid(fs.st_uid)[0]
                g   = grp.getgrgid(fs.st_gid)[0]
                p   = oct(fs.st_mode & 0o0777)
                txt = "No write permission on %s (owner=%s,group=%s,perms=%s)!" % (
                        ser, o, g, p)
                self._connecting_future.set_progress_text(txt)
                return
            except ImportError:
                self.log.exception()

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
