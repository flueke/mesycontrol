#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
import util
from command import Command

class ErrorResponse(Exception):
    def __init__(self, response):
        self.response = response

    def __str__(self):
        return "ErrorResponse(%s)" % self.response.get_error_string()

class ConnectionError(Exception):
    def __init__(self, text="Disconnected from device", errinfo=None):
        super(ConnectionError, self).__init__(text)
        self.errinfo = errinfo

class MRCCommand(Command):
    def __init__(self, mrc, parent=None):
        super(MRCCommand, self).__init__(parent)
        self.mrc       = mrc
        self._response = None
        mrc.disconnected.connect(self._on_mrc_disconnected)

    def _on_mrc_disconnected(self, info=None):
        self._exception = ConnectionError("Disconnected from device", info)
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
        super(SetParameter, self).__init__(device, parent)
        self.device  = device
        self.address = address
        self.value   = value
        self.log = util.make_logging_source_adapter(__name__, self)

    def _start(self):
        self.log.debug("%s started", str(self))
        self.device.set_parameter(address=self.address, value=self.value, response_handler=self._handle_set_response)

    def _handle_set_response(self, request, response):
        self._response = response
        if response.is_error():
            self._stopped(True)
        else:
            self.device.read_parameter(self.address, self._handle_read_response)

    def _handle_read_response(self, request, response):
        self._response = response
        self._stopped(True)

    def _get_result(self):
        res = super(SetParameter, self)._get_result()
        return res.val if res is not None else None

    def __str__(self):
        return "SetParameter(device=%s, addr=%d,val=%d)" % (self.device, self.address, self.value)

class ReadParameter(MRCCommand):
    def __init__(self, device, address, parent=None):
        super(ReadParameter, self).__init__(device, parent)
        self.device  = device
        self.address = address
        self.log     = util.make_logging_source_adapter(__name__, self)

    def _start(self):
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

class FetchMissingParameters(Command):
    def __init__(self, device, mirror=False, parent=None):
        super(FetchMissingParameters, self).__init__(parent)
        self.device = device
        self.mirror = mirror

    def _start(self):
        for i in range(256):
            if not self.device.has_parameter(i):
                if self.mirror:
                    self.device.read_mirror_parameter(i, self._handle_response)
                else:
                    self.device.read_parameter(i, self._handle_response)

    def _handle_response(self, request, response):
        if response.is_error():
            self._stopped(False)
        elif self.device.has_all_parameters():
            self._stopped(True)
