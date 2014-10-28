#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
import weakref

import hw_model
import protocol
import util

class MRCController(QtCore.QObject):
    write_access_changed            = pyqtSignal(bool)
    silence_changed                 = pyqtSignal(bool)
    request_queue_size_changed      = pyqtSignal(int)
    request_queue_empty             = pyqtSignal()
    request_sent                    = pyqtSignal(object, object)          #: request_id, request
    request_canceled                = pyqtSignal(object, object)          #: request_id, request
    request_completed               = pyqtSignal(object, object, object)  #: request_id, request, response
    polling_changed                 = pyqtSignal(bool)

    def __init__(self, mrc_connection, mrc_model, parent=None):
        super(MRCController, self).__init__(parent)
        self.log        = util.make_logging_source_adapter(__name__, self)
        self._model     = None
        self._poll_flag = True
        self.connection = mrc_connection
        self.model      = mrc_model

        # Mappings of subscriber_object to (DeviceController, address) pairs.
        self.static_subscriptions   = weakref.WeakKeyDictionary()
        self.volatile_subscriptions = weakref.WeakKeyDictionary()

        self.connection.connecting.connect(self._on_connecting)
        self.connection.connected.connect(self._on_connected)
        self.connection.disconnected.connect(self._on_disconnected)
        self.connection.connection_error.connect(self._on_connection_error)
        self.connection.write_access_changed.connect(self.write_access_changed)
        self.connection.silence_changed.connect(self.silence_changed)
        self.connection.message_received.connect(self._on_message_received)
        self.connection.response_received.connect(self._on_response_received)
        self.connection.request_sent.connect(self.request_sent)
        self.connection.request_canceled.connect(self.request_canceled)
        self.connection.request_completed.connect(self.request_completed)
        self.connection.write_queue_size_changed.connect(self._on_request_queue_size_changed)

        timer = QtCore.QTimer(self, timeout=self._maybe_fetch_subscriptions)
        timer.start(500)

    def get_model(self):
        return self._model() if self._model is not None else None

    def set_model(self, mrc_model):
        self._model = weakref.ref(mrc_model) if mrc_model is not None else None

        if self.is_connected():
            self.model.set_connected()
        elif self.is_connecting():
            self.model.set_connecting()
        else:
            self.model.set_disconnected()

    # connection related methods
    def connect(self):
        self.connection.connect()

    def disconnect(self):
        self.connection.disconnect()

    def is_connected(self):
        return self.connection.is_connected()

    def is_connecting(self):
        return self.connection.is_connecting()

    def get_connection_info(self):
        return self.connection.get_info()

    def set_write_access(self, want_access, force=False, response_handler=None):
        if want_access:
            mt = "request_force_write_access" if force else "request_acquire_write_access"
        else:
            mt = "request_release_write_access"

        m = protocol.Message(mt)
        return self._queue_request(m, response_handler)

    def has_write_access(self):
        return self.connection.has_write_access()

    def set_silenced(self, on_off, response_handler=None):
        m = protocol.Message('request_set_silent_mode', bool_value=on_off)
        return self._queue_request(m, response_handler)

    def is_silenced(self):
        return self.connection.is_silenced()

    # MRC-1 commands
    def scanbus(self, bus, response_handler=None):
        m = protocol.Message('request_scanbus', bus=bus)
        return self._queue_request(m, response_handler)

    def set_rc(self, bus, device, on_off, response_handler=None):
        mt = 'request_rc_on' if on_off else 'request_rc_off'
        m  = protocol.Message(mt, bus=bus, dev=device)
        return self._queue_request(m, response_handler)

    def reset(self, bus, device, response_handler=None):
        m = protocol.Message('request_reset', bus=bus, dev=device)
        return self._queue_request(m, response_handler)

    def copy_mem(self, bus, device, response_handler=None):
        m = protocol.Message('request_copy', bus=bus, dev=device)
        return self._queue_request(m, response_handler)

    def read_parameter(self, bus, device, address, response_handler=None):
        m = protocol.Message('request_read', bus=bus, dev=device, par=address)
        return self._queue_request(m, response_handler)

    def set_parameter(self, bus, device, address, value, response_handler=None):
        m = protocol.Message('request_set', bus=bus, dev=device, par=address, val=value)
        return self._queue_request(m, response_handler)

    def read_mirror_parameter(self, bus, device, address, response_handler=None):
        m = protocol.Message('request_mirror_read', bus=bus, dev=device, par=address)
        return self._queue_request(m, response_handler)

    def set_mirror_parameter(self, bus, device, address, value, response_handler=None):
        m = protocol.Message('request_mirror_set', bus=bus, dev=device, par=address, val=value)
        return self._queue_request(m, response_handler)

    def _on_connecting(self):
        self.model.set_connecting()

    def _on_connected(self):
        self.model.set_connected()
        for i in range(2):
            self.scanbus(i)

    def _on_disconnected(self):
        self.log.info("Disconnected from %s. Canceling pending requests.", self.connection.get_info())
        self.model.set_disconnected()
        self.connection.cancel_all_requests()

    def _on_connection_error(self, error_info):
        self.log.info("Connection error from %s: %s. Canceling pending requests.",
                self.connection.get_info(), error_info)
        self.model.set_disconnected(error=error_info)
        self.connection.cancel_all_requests()

    def _on_message_received(self, msg):
        mt = msg.get_type_name()

        if mt in ('response_scanbus', 'notify_scanbus'):
            self.model.set_scanbus_data(msg.bus, msg.bus_data)
        elif mt in ('response_read', 'notify_read', 'response_set', 'notify_set'):
            self.model.set_parameter(msg.bus, msg.dev, msg.par, msg.val)
        elif mt in ('response_mirror_read', 'notify_mirror_read', 'response_mirror_set', 'notify_mirror_set'):
            self.model.set_mirror_parameter(msg.bus, msg.dev, msg.par, msg.val)

    def _on_response_received(self, request, response):
        req_t = request.get_type_name()

        if response.get_type_name() == 'response_bool' and response.bool_value:
            if req_t in ('request_rc_on', 'request_rc_off'):
                self.model.set_rc(request.bus, request.dev, req_t == 'request_rc_on')
            elif req_t in ('request_reset', 'request_copy'):
                self.model.reset_mem(request.bus, request.dev)
                self.model.reset_mirror(request.bus, request.dev)

    def _on_request_queue_size_changed(self, size):
        self.request_queue_size_changed.emit(size)
        if size == 0:
            self.request_queue_empty.emit()

    def _queue_request(self, message, response_handler):
        return self.connection.queue_request(message, response_handler)

    def get_request_queue_size(self):
        return self.connection.get_write_queue_size()

    def cancel_request(self, request_id):
        return self.connection.cancel_request(request_id)

    def cancel_all_requests(self):
        self.connection.cancel_all_requests()

    def make_device_controller(self, device=None):
        return DeviceController(mrc_controller=self, device_model=device)

    def should_poll(self):
        return self._poll_flag

    def set_polling_enabled(self, on_off):
        changed = self.polling != on_off
        self._poll_flag = bool(on_off)
        if changed:
            self.polling_changed.emit(self.polling)

    def add_static_parameter_subscription(self, subscriber, device_controller, address):
        if subscriber not in self.static_subscriptions:
            self.static_subscriptions[subscriber] = set()

        self.static_subscriptions[subscriber].add((device_controller, address))

    def add_volatile_parameter_subscription(self, subscriber, device_controller, address):
        if subscriber not in self.volatile_subscriptions:
            self.volatile_subscriptions[subscriber] = set()

        self.volatile_subscriptions[subscriber].add((device_controller, address))

    def del_static_parameter_subscription(self, subscriber, device_controller, address):
        self.static_subscriptions[subscriber].remove((device_controller, address))

    def del_volatile_parameter_subscription(self, subscriber, device_controller, address):
        self.volatile_subscriptions[subscriber].remove((device_controller, address))

    model   = pyqtProperty(hw_model.MRCModel, get_model, set_model)
    polling = pyqtProperty(bool, should_poll, set_polling_enabled, notify=polling_changed)

    def _maybe_fetch_subscriptions(self):
        if not self.is_connected():
            return

        if self.get_request_queue_size() > 0:
            return

        if len(self.static_subscriptions):
            # Read unknown static parameters
            statics = reduce(lambda x, y: x.union(y), self.static_subscriptions.values())

            def filter_unknown(subscription_tuple):
                device_controller, address = subscription_tuple
                return address not in device_controller.model.memory

            statics = filter(filter_unknown, statics)

            if len(statics):
                self.log.info("reading %d static parameters", len(statics))
                self.log.debug("statics=%s", statics)

                for device_controller, address in statics:
                    # Pass reading to the device controller so that the device
                    # local queue size is updated.
                    device_controller.read_parameter(address)

        if self.should_poll() and len(self.volatile_subscriptions):
            volatiles = reduce(lambda x, y: x.union(y), self.volatile_subscriptions.values())
            self.log.info("reading %d volatile parameters", len(volatiles))
            self.log.debug("volatiles=%s", volatiles)

            for device_controller, address in volatiles:
                if device_controller.should_poll():
                    device_controller.read_parameter(address)

class DeviceController(QtCore.QObject):
    write_access_changed       = pyqtSignal(bool)
    silence_changed            = pyqtSignal(bool)

    request_queue_size_changed = pyqtSignal(int)
    request_sent               = pyqtSignal(object, protocol.Message)                   #: request_id, request
    request_canceled           = pyqtSignal(object, protocol.Message)                   #: request_id, request
    request_completed          = pyqtSignal(object, protocol.Message, protocol.Message) #: request_id, request, response
    polling_changed            = pyqtSignal(bool)

    def __init__(self, mrc_controller, device_model=None, parent=None):
        super(DeviceController, self).__init__(parent)
        self.log                    = util.make_logging_source_adapter(__name__, self)
        self._mrc_controller        = weakref.ref(mrc_controller)
        self.model                  = device_model
        self._request_ids           = set()
        self._poll_flag             = True

        mrc_controller.write_access_changed.connect(self.write_access_changed)
        mrc_controller.silence_changed.connect(self.silence_changed)

        mrc_controller.request_sent.connect(self._on_request_sent)
        mrc_controller.request_completed.connect(self._on_request_completed)
        mrc_controller.request_canceled.connect(self._on_request_canceled)
        mrc_controller.polling_changed.connect(self._on_mrc_polling_changed)

    def get_model(self):
        return self._model() if self._model is not None else None

    def set_model(self, device_model):
        self._model = weakref.ref(device_model) if device_model is not None else None

    def set_rc(self, on_off, response_handler=None):
        return self._add_request_id(self.mrc_controller.set_rc(
            self.model.bus, self.model.address, on_off, response_handler))

    def reset(self, response_handler=None):
        return self._add_request_id(self.mrc_controller.reset(
            self.model.bus, self.model.address, response_handler))

    def copy_mem(self, response_handler=None):
        return self._add_request_id(self.mrc_controller.copy_mem(
            self.model.bus, self.model.address, response_handler))

    def read_parameter(self, address, response_handler=None):
        return self._add_request_id(self.mrc_controller.read_parameter(
            self.model.bus, self.model.address, address, response_handler))

    def set_parameter(self, address, value, response_handler=None):
        return self._add_request_id(self.mrc_controller.set_parameter(
            self.model.bus, self.model.address, address, value, response_handler))

    def read_mirror_parameter(self, address, response_handler=None):
        return self._add_request_id(self.mrc_controller.read_mirror_parameter(
            self.model.bus, self.model.address, address, response_handler))

    def set_mirror_parameter(self, address, value, response_handler=None):
        return self._add_request_id(self.mrc_controller.set_mirror_parameter(
            self.model.bus, self.model.address, address, value, response_handler))

    def get_mrc_controller(self):
        return self._mrc_controller()

    def is_connected(self):
        return self.mrc_controller.is_connected()

    def _add_request_id(self, request_id):
        self._request_ids.add(request_id)
        self.request_queue_size_changed.emit(self.get_request_queue_size())
        return request_id

    def _on_request_sent(self, request_id, request):
        if request_id in self._request_ids:
            self.request_sent.emit(request_id, request)

    def _on_request_completed(self, request_id, request, response):
        if request_id in self._request_ids:
            self.log.debug("removing completed request %d from local queue", request_id)
            self._request_ids.remove(request_id)
            self.request_completed.emit(request_id, request, response)
            self.request_queue_size_changed.emit(self.get_request_queue_size())

    def _on_request_canceled(self, request_id, request):
        if request_id in self._request_ids:
            self.log.debug("removing canceled request %d from local queue", request_id)
            self._request_ids.remove(request_id)
            self.request_canceled.emit(request_id, request)
            self.request_queue_size_changed.emit(self.get_request_queue_size())
            self.log.debug("removed canceled request %d from local queue. new queue size=%d", 
                    request_id, self.get_request_queue_size())

    def get_request_queue_size(self):
        return len(self._request_ids)

    def cancel_request(self, request_id):
        if request_id not in self._request_ids:
            raise RuntimeError("No such request (request_id=%d)" % request_id)
        self.mrc_controller.cancel_request(request_id)

    def cancel_all_requests(self):
        for request_id in self.get_request_ids():
            self.cancel_request(request_id)

    def get_request_ids(self):
        return set(self._request_ids)

    def has_write_access(self):
        return self.mrc_controller.has_write_access()

    def is_silenced(self):
        return self.mrc_controller.is_silenced()

    def add_static_parameter_subscription(self, subscriber, address):
        self.mrc_controller.add_static_parameter_subscription(subscriber, self, address)

    def add_volatile_parameter_subscription(self, subscriber, address):
        self.mrc_controller.add_volatile_parameter_subscription(subscriber, self, address)

    def del_static_parameter_subscription(self, subscriber, address):
        self.mrc_controller.del_static_parameter_subscription(subscriber, self, address)

    def del_volatile_parameter_subscription(self, subscriber, address):
        self.mrc_controller.del_volatile_parameter_subscription(subscriber, self, address)

    def should_poll(self):
        return self.mrc_controller.should_poll() and self._poll_flag

    def set_polling_enabled(self, on_off):
        old_state = self.polling
        self._poll_flag = bool(on_off)

        if old_state != self.polling:
            self.polling_changed.emit(self.polling)

    def _on_mrc_polling_changed(self, on_off):
        self.polling_changed.emit(self.polling)


    mrc_controller  = pyqtProperty(MRCController, get_mrc_controller)
    model           = pyqtProperty(hw_model.DeviceModel, get_model, set_model)
    polling         = pyqtProperty(bool, should_poll, set_polling_enabled)
