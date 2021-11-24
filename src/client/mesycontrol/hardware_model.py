#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2016 mesytec GmbH & Co. KG <info@mesytec.com>
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

from mesycontrol.qt import Property
from mesycontrol.qt import Signal

import mesycontrol.basic_model as bm
import mesycontrol.future as future
import mesycontrol.proto as proto
import mesycontrol.util as util

import os

DEFAULT_CONNECT_TIMEOUT_MS = 10000

class AddressConflict(RuntimeError):
    def __str__(self):
        return "Address conflict"

class MRC(bm.MRC):
    connected                   = Signal()
    connecting                  = Signal(object)    #: future object
    disconnected                = Signal()
    connection_error            = Signal(object)    #: error object

    address_conflict_changed    = Signal(bool)

    status_changed              = Signal(object)     #: proto.MRCStatus
    write_access_changed        = Signal(bool, bool) #: has_write_access, can_acquire
    silenced_changed            = Signal(bool)       #: is_silenced

    def __init__(self, url, parent=None):
        super(MRC, self).__init__(url, parent)
        self.log   = util.make_logging_source_adapter(__name__, self)
        self._controller = None

        self._connected  = False
        self._connecting = False
        self._disconnected = True
        self.last_connection_error = None
        self._status = None
        self._has_write_access = False
        self._can_acquire_write_access = False
        self._silenced = False
        self._connect_future = None

    def set_controller(self, controller):
        """Set the hardware controller this MRC should use.
        The MRC holds a strong reference to the controller."""
        if self.controller is not None:
            self.controller.mrc = None

        self._controller = controller

        if self.controller is not None:
            self.controller.mrc = self

    def get_controller(self):
        return self._controller

    def set_status(self, status):
        code_old = None if self._status is None else self._status.code
        code_new = None if status is None else status.code

        reason_old = None if self._status is None else self._status.reason
        reason_new = None if status is None else status.reason

        self.log.debug("set_status: code_old=%s, code_new=%s", code_old, code_new)
        self.log.debug("set_status: reason_old=%s, reason_new=%s", reason_old, reason_new)

        if reason_new is not None:
            self.log.debug("set_status: reason_new=%s", os.strerror(reason_new))

        self._status = status
        self.status_changed.emit(status)

        if self._connect_future is None:
            self._connect_future = future.Future()

        if status.code in (proto.MRCStatus.CONNECTING, proto.MRCStatus.INITIALIZING):
            self.set_connecting(self._connect_future)

        elif status.code == proto.MRCStatus.RUNNING:
            self.set_connected()
            self._connect_future.set_result(True)
            self._connect_future = None

        elif status.code in (proto.MRCStatus.STOPPED, proto.MRCStatus.CONNECT_FAILED,
                proto.MRCStatus.INIT_FAILED):
            self.set_disconnected()
            self._connect_future.set_result(False)
            self._connect_future = None

    def get_status(self):
        return self._status

    def set_write_access(self, has_write_access, can_acquire):
        """Updates the local write access and can_acquire flags.
        Emits write_access_changed() if one of the two flags changed."""
        if (self._has_write_access != has_write_access or
                self._can_acquire_write_access != can_acquire):

            self._has_write_access = has_write_access
            self._can_acquire_write_access = can_acquire

            self.write_access_changed.emit(
                    self._has_write_access,
                    self._can_acquire_write_access)

    def acquire_write_access(self, force=False):
        return self.controller.acquire_write_access(force)

    def release_write_access(self):
        return self.controller.release_write_access()

    def has_write_access(self):
        return self._has_write_access

    def can_acquire_write_access(self):
        return self._can_acquire_write_access

    def update_silenced(self, silenced):
        if self._silenced != silenced:
            self._silenced = silenced
            self.silenced_changed.emit(self._silenced)

    def set_silenced(self, silenced):
        return self.controller.set_silenced(silenced)

    def is_silenced(self):
        return self._silenced

    def add_device(self, device):
        super(MRC, self).add_device(device)

        self.connected.connect(device.connected)
        self.connecting.connect(device.connecting)
        self.disconnected.connect(device.disconnected)
        self.connection_error.connect(device.connection_error)

    def remove_device(self, device):
        super(MRC, self).remove_device(device)

        self.connected.disconnect(device.connected)
        self.connecting.disconnect(device.connecting)
        self.disconnected.disconnect(device.disconnected)
        self.connection_error.disconnect(device.connection_error)

    def get_connection(self):
        return self.controller.connection

    def connect(self, timeout_ms=DEFAULT_CONNECT_TIMEOUT_MS):
        ret = self.controller.connect(timeout_ms)
        self.set_connecting(ret)
        return ret

    def disconnect(self):
        return self.controller.disconnect()

    def is_connected(self):
        return self._connected

    def set_connected(self):
        self.log.debug("%s: set_connected", self.url)
        self._connected, self._connecting, self._disconnected = (True, False, False)
        self.last_connection_error = None
        self.connected.emit()

    def is_connecting(self):
        return self._connecting

    def set_connecting(self, the_future):
        self.log.debug("%s: set_connecting", self.url)
        self._connected, self._connecting, self._disconnected = (False, True, False)
        self.last_connection_error = None

        def done(f):
            try:
                f.result()
            except Exception as e:
                self.set_connection_error(e)

        the_future.add_done_callback(done)
        self.connecting.emit(the_future)

    def is_disconnected(self):
        return self._disconnected

    def set_disconnected(self):
        self.log.debug("%s: set_disconnected", self.url)
        self._connected, self._connecting, self._disconnected = (False, False, True)
        self.disconnected.emit()
        for device in self:
            device.clear_cached_memory()

    def set_connection_error(self, error):
        self.log.debug("%s: set_connection_error: %s (%s)", self.url, error, type(error))
        self._connected, self._connecting, self._disconnected = (False, False, True)
        self.last_connection_error = error
        self.connection_error.emit(error)
        for device in self:
            device.clear_cached_memory()

    def read_parameter(self, bus, device, address):
        return self.controller.read_parameter(bus, device, address)

    def set_parameter(self, bus, device, address, value):
        return self.controller.set_parameter(bus, device, address, value)

    def scanbus(self, bus):
        return self.controller.scanbus(bus)

    def __str__(self):
        return "hm.MRC(id=%s, url=%s, connected=%s)" % (
                hex(id(self)), self.url, self.is_connected())

    connection      = Property(object, get_connection)
    controller      = Property(object, get_controller, set_controller)
    write_access    = Property(bool, has_write_access, set_write_access)
    silenced        = Property(bool, is_silenced)

class Device(bm.Device):
    connected                   = Signal()
    connecting                  = Signal(object)
    disconnected                = Signal()
    connection_error            = Signal(object)    #: error object

    address_conflict_changed    = Signal(bool)
    rc_changed                  = Signal(bool)

    def __init__(self, bus, address, idc, parent=None):
        super(Device, self).__init__(bus, address, idc, parent)

        self._address_conflict = False
        self._rc = False

    def _read_parameter(self, address):
        if self.address_conflict:
            return future.Future().set_exception(AddressConflict())
        return self.mrc.read_parameter(self.bus, self.address, address)

    def _set_parameter(self, address, value):
        if self.address_conflict:
            return future.Future().set_exception(AddressConflict())
        return self.mrc.set_parameter(self.bus, self.address, address, value)

    def get_controller(self):
        return self.mrc.controller

    def has_address_conflict(self):
        return self._address_conflict

    def set_address_conflict(self, conflict):
        conflict = bool(conflict)
        if self.address_conflict != conflict:
            self._address_conflict = conflict
            self.address_conflict_changed.emit(self.address_conflict)

    def get_rc(self):
        return self._rc

    def update_rc(self, rc):
        """Updates the local RC flag of this device."""
        rc = bool(rc)
        if self.rc != rc:
            self._rc = rc
            self.rc_changed.emit(self.rc)

    def set_rc(self, on_off):
        """Sends a ON/OFF command to the MRC.
        On successful command execution the local RC flag is updated.
        """
        if self.address_conflict:
            raise AddressConflict()

        def on_rc_set(f):
            if f.exception() is None:
                self.update_rc(on_off)

        ret = self.controller.set_rc(self.bus, self.address, on_off)
        ret.add_done_callback(on_rc_set)
        return ret

    def add_poll_item(self, subscriber, item):
        """Add parameters that should be polled repeatedly.
        As long as the given subscriber object is alive and the device is
        connected, the given item will be polled.
        Item may be a single parameter address or a tuple of (lower, upper)
        addresses to poll.
        If the server and mrc support reading parameter ranges and a tuple is
        given, the read range command will be used."""
        self.controller.add_poll_item(subscriber, self.bus, self.address, item)

    def add_poll_items(self, subscriber, items):
        self.controller.add_poll_items(subscriber, (
            (self.bus, self.address, item) for item in items))

    def remove_polling_subscriber(self, subscriber):
        return self.controller.remove_polling_subscriber(subscriber)

    def is_connected(self):
        return self.mrc.is_connected()

    def is_connecting(self):
        return self.mrc.is_connecting()

    def is_disconnected(self):
        return self.mrc.is_disconnected()

    def get_last_connection_error(self):
        return self.mrc.last_connection_error

    def __str__(self):
        return "hm.Device(id=%s, b=%d, a=%d, idc=%d, mrc=%s)" % (
                hex(id(self)), self.bus, self.address, self.idc, self.mrc)

    controller = Property(object, get_controller)

    address_conflict = Property(bool, has_address_conflict, set_address_conflict,
            notify=address_conflict_changed)

    rc = Property(bool, get_rc, update_rc, notify=rc_changed)
