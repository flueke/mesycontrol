#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from command import Command
from functools import partial

class ErrorResponse(Exception):
    def __init__(self, response):
        self.response = response

    def __str__(self):
        return "ErrorResponse(%s)" % self.response.get_error_string()

class MRCCommand(Command):
    def __init__(self, mrc, parent=None):
        super(MRCCommand, self).__init__(parent)
        self.mrc       = mrc
        self._response = None
        mrc.state_changed.connect(self._on_mrc_state_changed)

    def _on_mrc_state_changed(self, old_state, new_state, info):
        if not self.mrc.is_connected():
            self._exception = info if info is not None else RuntimeError("Disconnected from server")
            self._stopped(False)

    def _handle_disconnected(self):
        self._exception = RuntimeError("Disconnected from server")
        self._stopped(False)

    #def _handle_connection_error(self, err_object):
    #    self._exception = err_object
    #    self._stopped(False)

    def _handle_response(self, request, response):
        self._response = response
        self._stopped(True)

    def _stop(self):
        pass

    def get_response(self):
        return self._response

    def _get_result(self):
        if self.has_failed():
            raise ErrorResponse(self.get_response())
        return self.get_response()

    def _has_failed(self):
        return self._response is not None and self._response.is_error()

class SetParameter(MRCCommand):
    def __init__(self, device, address, value, parent=None):
        super(SetParameter, self).__init__(device, parent)
        self.device  = device
        self.address = address
        self.value   = value
        self.log = util.make_logging_source_adapter(__name__, self)

    def _start(self):
        self.log.debug("%s started", str(self))
        self.device.set_parameter(self.address, self.value, self._handle_response)

    def _get_result(self):
        res = super(SetParameter, self)._get_result()
        return res.val if res is not None else None

    def __str__(self):
        return "SetParameter(device=%s, addr=%d,val=%d)" % (self.device, self.address, self.value)

import util

class ReadParameter(MRCCommand):
    def __init__(self, device, address, parent=None):
        super(ReadParameter, self).__init__(device, parent)
        self.device  = device
        self.address = address
        self.log = util.make_logging_source_adapter(__name__, self)

    def _start(self):
        self.log.debug("Reading %d", self.address)
        self.device.read_parameter(self.address, self._handle_response)

    def _get_result(self):
        res = super(ReadParameter, self)._get_result()
        return res.val if res is not None else None

    def __str__(self):
        return "ReadParameter(addr=%d)" % (self.address)

class Scanbus(MRCCommand):
    def __init__(self, mrc, bus, parent=None):
        super(Scanbus, self).__init__(mrc, parent)
        self.mrc = mrc
        self.bus = bus

    def _start(self):
        self.mrc.scanbus(self.bus, self._handle_response)

class SetRc(MRCCommand):
    def __init__(self, device, rc, parent=None):
        super(SetRc, self).__init__(device, parent)
        self.device = device
        self.rc = rc

    def _start(self):
        self.device.set_rc(self.rc, self._handle_response)

class Connect(Command):
    def __init__(self, mrc, parent=None):
        super(Connect, self).__init__(parent)
        self.mrc = mrc
        self._connection_error = None
        connection = self.mrc.model.controller.connection # FIXME: encapsulate this: MRC needs those signals
        connection.connected.connect(partial(self._stopped, True))
        connection.disconnected.connect(partial(self._stopped, True))
        connection.connection_error.connect(self._on_connection_error)
        connection.connection_error.connect(partial(self._stopped, True))

    def _start(self):
        self.mrc.connect()

    def _stop(self):
        pass

    def _on_connection_error(self, error):
        self._connection_error = error
        self._stopped(True)

    def _get_result(self):
        if self.mrc.is_connected():
            return True
        elif self._connection_error is not None:
            raise self._connection_error
        else:
            return False

class AcquireWriteAccess(MRCCommand):
    def __init__(self, mrc, force=False, parent=None):
        super(AcquireWriteAccess, self).__init__(mrc, parent)
        self.mrc   = mrc
        self.force = force

    def _start(self):
        self.mrc.acquire_write_access(self.force, self._handle_response)

class ReleaseWriteAccess(MRCCommand):
    def __init__(self, mrc, parent=None):
        super(ReleaseWriteAccess, mrc, self).__init__(parent)
        self.mrc   = mrc

    def _start(self):
        self.mrc.release_write_access(self._handle_response)

class RefreshMemory(Command):
    def __init__(self, device, parent=None):
        super(RefreshMemory, self).__init__(parent)
        self.device = device

    def _start(self):
        for i in range(256):
            self.device.read_parameter(i, self._handle_response)

    def _handle_response(self, request, response):
        if response.is_error():
            self._stopped(False)
        elif response.par == 255:
            self._stopped(True)
