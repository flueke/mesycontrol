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
        self._response = None
        mrc.sig_disconnected.connect(self._handle_disconnected)

    def _handle_disconnected(self):
        self._exception = RuntimeError("Disconnected from server")
        self._stopped(False)

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
        super(SetParameter, self).__init__(device.mrc, parent)
        self.device  = device
        self.address = address
        self.value   = value

    def _start(self):
        self.device.set_parameter(self.address, self.value, self._handle_response)

    def _get_result(self):
        res = super(SetParameter, self)._get_result()
        return res.val if res is not None else None

import util

class ReadParameter(MRCCommand):
    def __init__(self, device, address, parent=None):
        super(ReadParameter, self).__init__(device.mrc, parent)
        self.device  = device
        self.address = address
        self.log = util.make_logging_source_adapter(__name__, self)

    def _start(self):
        self.device.read_parameter(self.address, self._handle_response)
        self.log.debug("Reading %s", self.address)

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
        super(SetRc, self).__init__(device.mrc, parent)
        self.device = device
        self.rc = rc

    def _start(self):
        self.device.set_rc(self.rc, self._handle_response)

class Connect(Command):
    def __init__(self, connection, parent=None):
        super(Connect, self).__init__(parent)
        self.connection = connection
        self.connection.sig_connected.connect(partial(self._stopped, True))
        self.connection.sig_disconnected.connect(partial(self._stopped, True))
        self.connection.sig_connection_error.connect(partial(self._stopped, True))

    def _start(self):
        self.connection.connect()

    def _stop(self):
        pass

    def _get_result(self):
        return self.connection.is_connected()

class AcquireWriteAccess(MRCCommand):
    def __init__(self, mrc, force=False, parent=None):
        super(AcquireWriteAccess, self).__init__(mrc, parent)
        self.mrc   = mrc
        self.force = force

    def _start(self):
        self.mrc.connection.set_write_access(True, self.force, self._handle_response)

class ReleaseWriteAccess(MRCCommand):
    def __init__(self, mrc, parent=None):
        super(ReleaseWriteAccess, mrc, self).__init__(parent)
        self.mrc   = mrc

    def _start(self):
        self.mrc.connection.set_write_access(False, response_handler=self._handle_response)
