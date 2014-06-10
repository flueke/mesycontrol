#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import weakref
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import pyqtProperty
from protocol import Message
from device_model import DeviceModel
import util

class MRCModel(QtCore.QObject):
    sig_connecting            = pyqtSignal()
    sig_connected             = pyqtSignal()
    sig_disconnected          = pyqtSignal()
    sig_connection_error      = pyqtSignal(object)
    #: sig_ready is emmited once the connection has been established and both
    #: busses have been scanned.
    sig_ready                 = pyqtSignal()
    #: sig_idle signals that no more outgoing messages are queued
    sig_idle                  = pyqtSignal()
    sig_message_sent          = pyqtSignal(Message)
    sig_message_received      = pyqtSignal(Message)
    sig_response_received     = pyqtSignal(Message, Message)
    sig_notification_received = pyqtSignal(Message)
    sig_error_received        = pyqtSignal(Message)
    sig_write_access_changed  = pyqtSignal(bool)
    sig_silence_changed       = pyqtSignal(bool)

    #: Args: bus, dev, par, val
    sig_parameter_read   = pyqtSignal(int, int, int, int)
    #: Args: bus, dev, par, val
    sig_parameter_set    = pyqtSignal(int, int, int, int)
    #: Args: bus, dev, rc_status
    sig_rc_set           = pyqtSignal(int, int, bool)

    def __init__(self, connection, parent=None):
        super(MRCModel, self).__init__(parent)
        self.device_models = {0:{}, 1:{}}
        self._ready = False
        self.log = util.make_logging_source_adapter(__name__, self)

        self._connection = weakref.ref(connection)
        connection.sig_connecting.connect(self.sig_connecting)
        connection.sig_connected.connect(self._slt_connected)
        connection.sig_disconnected.connect(self._slt_disconnected)
        connection.sig_connection_error.connect(self.sig_connection_error)
        connection.sig_idle.connect(self.sig_idle)
        connection.sig_message_sent.connect(self.sig_message_sent)
        connection.sig_message_received.connect(self._slt_message_received)
        connection.sig_response_received.connect(self.sig_response_received)
        connection.sig_notification_received.connect(self.sig_notification_received)
        connection.sig_error_received.connect(self.sig_error_received)
        connection.sig_write_access_changed.connect(self.sig_write_access_changed)
        connection.sig_silence_changed.connect(self.sig_silence_changed)

    def get_connection(self):
        return self._connection() if self._connection is not None else None

    connection = pyqtProperty(object, get_connection)

    def get_mrc_address_string(self):
        return self.connection.get_info()

    def scanbus(self, bus, response_handler=None):
        self.connection.send_message(
                Message('request_scanbus', bus=bus),
                response_handler)

    def read_parameter(self, bus, dev, par, response_handler=None):
        self.connection.send_message(
                Message('request_read', bus=bus, dev=dev, par=par),
                response_handler)

    def set_parameter(self, bus, dev, par, value, response_handler=None):
        self.connection.send_message(
                Message('request_set', bus=bus, dev=dev, par=par, val=value),
                response_handler)

    def set_rc(self, bus, dev, rc, response_handler=None):
        self.connection.send_message(
                Message('request_rc_on' if rc else 'request_rc_off', bus=bus, dev=dev),
                response_handler)

    def _slt_connected(self):
        self.sig_connected.emit()
        for i in range(2):
            self.scanbus(i)

    def _slt_disconnected(self):
        self._ready = False
        self.sig_disconnected.emit()

    def _slt_message_received(self, msg):
        self.log.debug("Received message=%s", msg)

        if msg.get_type_name() == 'response_scanbus':
            for dev in range(16):
                idc, rc = msg.bus_data[dev]

                model = self.device_models[msg.bus].get(dev, None)

                if idc <= 0 and model is not None:
                    # TODO: device disappeared
                    pass
                elif idc > 0:
                    # Device present
                    if rc in (0, 1):
                        # Device present and ok
                        if model is None:
                            model = DeviceModel(msg.bus, dev, idc, rc, mrc_model=self, parent=self)
                            self.device_models[msg.bus][dev] = model
                        elif model.idc != idc:
                            # TODO: handle device changed. Create a model for
                            # the new device. Somehow tell the old device that
                            # it's disconnected. Also signal that the device
                            # was removed.
                            pass
                        elif model.rc != rc:
                            # Device stayed the same but rc changed.
                            model.rc = rc
                            model.sig_rc_set.emit(rc)
                    else:
                        # TODO: Address conflict
                        pass
                        
            if msg.bus == 1 and not self._ready:
                self._ready = True
                self.sig_ready.emit()

        elif msg.get_type_name() == 'response_read':
            self.sig_parameter_read.emit(msg.bus, msg.dev, msg.par, msg.val)
        elif msg.get_type_name() in ('response_set', 'notify_set'):
            self.sig_parameter_set.emit(msg.bus, msg.dev, msg.par, msg.val)
        else:
            self.log.debug("Unhandled message %s", msg)
