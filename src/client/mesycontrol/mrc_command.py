#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from command import Command

class MRCCommand(Command):
    def __init__(self, parent=None):
        super(MRCCommand, self).__init__(parent)
        self._response = None

    def _handle_response(self, request, response):
        self._response = response
        self._stopped()

    def _stop(self):
        pass

    def get_response(self):
        return self._response

    def _get_result(self):
        return self.get_response()

    def has_failed(self):
        return self._response is not None and self._response.is_error()

class SetParameter(MRCCommand):
    def __init__(self, device, address, value, parent=None):
        super(SetParameter, self).__init__(parent)
        self.device  = device
        self.address = address
        self.value   = value

    def _start(self):
        self.device.setParameter(self.address, self.value, self._handle_response)

    def _get_result(self):
        if self.has_failed() or self.get_response() is None:
            return self.get_response()
        return self.get_response().val

class ReadParameter(MRCCommand):
    def __init__(self, device, address, parent=None):
        super(ReadParameter, self).__init__(parent)
        self.device  = device
        self.address = address

    def _start(self):
        self.device.readParameter(self.address, self._handle_response)

    def _get_result(self):
        if self.has_failed() or self.get_response() is None:
            return self.get_response()
        return self.get_response().val

class Scanbus(MRCCommand):
    def __init__(self, mrc, bus, parent=None):
        super(Scanbus, self).__init__(parent)
        self.mrc = mrc
        self.bus = bus

    def _start(self):
        self.mrc.scanbus(self.bus, self._handle_response)

class SetRc(MRCCommand):
    def __init__(self, device, rc, parent=None):
        super(SetRc, self).__init__(parent)
        self.device = device
        self.rc = rc

    def _start(self):
        self.device.setRc(self.rc, self._handle_response)

class Connect(Command):
    def __init__(self, connection, parent=None):
        super(Connect, self).__init__(parent)
        self.connection = connection
        self.connection.sig_connected.connect(self._stopped)
        self.connection.sig_disconnected.connect(self._stopped)
        self.connection.sig_connection_error.connect(self._stopped)

    def _start(self):
        self.connection.connect()

    def _stop(self):
        pass

    def get_result(self):
        return self.connection.is_connected()
