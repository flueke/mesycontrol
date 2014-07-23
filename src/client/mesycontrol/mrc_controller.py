#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
import Queue
import weakref

from hw_model import MRCModel
from hw_model import DeviceModel
from protocol import Message

class AbstractMRCController(QtCore.QObject):
    def __init__(self, mrc_model, parent=None):
        super(AbstractMRCController, self).__init__(parent)
        self._model = None
        self.model  = mrc_model

    def get_model(self):
        return self._model() if self._model is not None else None

    def set_model(self, mrc_model):
        self._model = weakref.ref(mrc_model) if mrc_model is not None else None

    model = pyqtProperty(MRCModel, get_model, set_model)

    # connection commands
    def connect(self):
        raise NotImplementedError()

    def disconnect(self):
        raise NotImplementedError()

    def is_connected(self):
        raise NotImplementedError()

    def get_connection_info(self):
        raise NotImplementedError()

    def set_write_access(self, want_access, force=False, response_handler=None):
        raise NotImplementedError()

    def has_write_access(self):
        raise NotImplementedError()

    def set_silenced(self, on_off, response_handler=None):
        raise NotImplementedError()

    def is_silenced(self):
        raise NotImplementedError()

    # MRC-1 commands
    def scanbus(self, bus, response_handler=None):
        raise NotImplementedError()

    def set_rc(self, bus, device, on_off, response_handler=None):
        raise NotImplementedError()

    def reset(self, bus, device, response_handler=None):
        raise NotImplementedError()

    def copy_mem(self, bus, device, response_handler=None):
        raise NotImplementedError()

    def read_parameter(self, bus, device, address, response_handler=None):
        raise NotImplementedError()

    def set_parameter(self, bus, device, address, value, response_handler=None):
        raise NotImplementedError()

    # status, history, errors
    def has_pending_requests(self):
        raise NotImplementedError()

    def make_device_controller(self, device):
        return DeviceController(self, device)

class MesycontrolMRCController(AbstractMRCController):
    def __init__(self, mrc_connection, mrc_model, parent=None):
        super(MesycontrolMRCController, self).__init__(mrc_model, parent)
        self.connection = mrc_connection
        self.connection.sig_connecting.connect(self._on_connecting)
        self.connection.sig_connected.connect(self._on_connected)
        self.connection.sig_disconnected.connect(self._on_disconnected)
        self.connection.sig_connection_error.connect(self._on_connection_error)
        self.connection.sig_idle.connect(self._try_send_next_request)
        self.connection.sig_message_received.connect(self._on_message_received)

        self._queue           = Queue.Queue()
        self._current_request = None
        self._write_access    = False
        self._silenced        = False

    def get_model(self):
        return self._model() if self._model is not None else None

    def set_model(self, mrc_model):
        super(MesycontrolMRCController, self).set_model(mrc_model)

        if self.connection.is_connected():
            self.model.state = MRCModel.Connected
        elif self.connection.is_connecting():
            self.model.state = MRCModel.Connecting
        else:
            self.model.state = MRCModel.Disconnected

    model = pyqtProperty(MRCModel, get_model, set_model)

    # connection commands
    def connect(self):
        self.connection.connect()

    def disconnect(self):
        self.connection.disconnect()

    def is_connected(self):
        return self.connection.is_connected()

    def get_connection_info(self):
        return self.connection.get_info()

    def set_write_access(self, want_access, force=False, response_handler=None):
        if want_access:
            mt = "request_force_write_access" if force else "request_acquire_write_access"
        else:
            mt = "request_release_write_access"

        m = Message(mt)
        return self._queue_request(m, response_handler)

    def has_write_access(self):
        return self._write_access

    def set_silenced(self, on_off, response_handler=None):
        m = Message('request_set_silent_mode', bool_value=on_off)
        return self._queue_request(m, response_handler)

    def is_silenced(self):
        return self._silenced

    # MRC-1 commands
    def scanbus(self, bus, response_handler=None):
        m = Message('request_scanbus', bus=bus)
        return self._queue_request(m, response_handler)

    def set_rc(self, bus, device, on_off, response_handler=None):
        mt = 'request_rc_on' if on_off else 'request_rc_off'
        m  = Message(mt, bus=bus, dev=device)
        return self._queue_request(m, response_handler)

    def reset(self, bus, device, response_handler=None):
        m = Message('request_reset', bus=bus, dev=device)
        return self._queue_request(m, response_handler)

    def copy_mem(self, bus, device, response_handler=None):
        m = Message('request_copy', bus=bus, dev=device)
        return self._queue_request(m, response_handler)

    def read_parameter(self, bus, device, address, response_handler=None):
        m = Message('request_read', bus=bus, dev=device, par=address)
        return self._queue_request(m, response_handler)

    def set_parameter(self, bus, device, address, value, response_handler=None):
        m = Message('request_read', bus=bus, dev=device, par=address, val=value)
        return self._queue_request(m, response_handler)

    def _on_connecting(self):
        self.model.state = MRCModel.Connecting

    def _on_connected(self):
        self.model.state = MRCModel.Connected
        for i in range(2):
            self.scanbus(i)

    def _on_disconnected(self):
        self.model.state = MRCModel.Disconnected

    def _on_connection_error(self, error_info):
        self.model.set_state(MRCModel.Disconnected, error_info)

    def _on_message_received(self, request, response):
        pass

    def _queue_request(self, message, response_handler):
        t = (message, response_handler)
        self._queue.put(t)
        self._try_send_next_request()
        return t

    def _try_send_next_request(self):
        try:
            msg, response_handler = self._queue.get(False)
            self.connection.send_message(msg, response_handler)
        except Queue.Empty:
            pass

class DeviceController(QtCore.QObject):
    def __init__(self, mrc_controller, device_model, parent=None):
        super(DeviceController, self).__init__(parent)
        self._mrc_controller = weakref.ref(mrc_controller) if mrc_controller is not None else None
        self._model          = weakref.ref(device_model) if device_model is not None else None

    def set_rc(self, on_off, response_handler=None):
        return self.mrc_controller.set_rc(self.model.bus, self.model.address, on_off)

    def reset(self, response_handler=None):
        return self.mrc_controller.reset(self.model.bus, self.model.address)

    def copy_mem(self, response_handler=None):
        return self.mrc_controller.copy_mem(self.model.bus, self.model.address)

    def read_parameter(self, address, response_handler=None):
        return self.mrc_controller.read_parameter(self.model.bus, self.model.address, address)

    def set_parameter(self, address, value, response_handler=None):
        return self.mrc_controller.set_parameter(self.model.bus, self.model.address, address, value)

    def get_mrc_controller(self, response_handler=None):
        return self._mrc_controller() if self._mrc_controller is not None else None

    def get_model(self, response_handler=None):
        return self._model() if self._model is not None else None

    def set_model(self, model, response_handler=None):
        self._model = weakref.ref(model) if model is not None else None

    mrc_controller = pyqtProperty(AbstractMRCController, get_mrc_controller)
    model          = pyqtProperty(DeviceModel, get_model)
