#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from collections import namedtuple

from qt import QtCore
from qt import pyqtSignal

ParameterTuple = namedtuple('ParameterTuple', ['cfg', 'hw'])

class Device(QtCore.QObject):
    """High level device abstraction.
    """
    parameter_changed = pyqtSignal(int, object) # address, ParameterTuple


    address_conflict = property()
    profile          = property()
    config          = property()
    model           = property()

    def __init__(self, idc, bus, address, context, parent=None):
        super(Device, self).__init__(parent)
        self.profile    = context.get_device_profile(self.idc)
        self.config     = make_default_config(self.profile)
        self.model      = DeviceModel(self.idc, bus, address)

    def get_parameter(self, address):
        """Returns a ParameterTuple filled with the config and hardware values."""
        return ParameterTuple(self.config[address], self.model[address])

    def set_parameter(self, address, value):
        """Sets the config parameter at `address' to `value'."""
        self.cfg_memory[address] = value

    def read_parameter(self, address):
        """Reads the given address from the hardware."""
        def handle_read_parameter(f):
            try:
                self.model[address] = f.get_result()
            except ProtocolError as e:
                self._handle_protocol_error(e)
            except CancelledError:
                pass

        f = self.controller.read_parameter(address)
        f.add_done_callback(handle_read_parameter)
        return f

    def write_parameter(self, address, value):
        """Writes the given `value' to the given `adddress'."""
        def handle_write_parameter(f):
            try:
                target_value, actual_value = f.get_result()
                self.hw_memory[address] = actual_value
            except ProtocolError as e:
                self._handle_protocol_error(e)
            except CancelledError:
                pass

        f = self.controller.write_parameter(address, value)
        f.add_done_callback(handle_write_parameter)
        return f

    def _handle_protocol_error(self, e):
        if e.type_name == 'mrc_address_conflict':
            self.address_conflict = True
        if e.name in ('mrc_no_response mrc_comm_timeout mrc_comm_error mrc_address_conflict'.split()):
            self.connection_error = e # Must be cleared on reconnect
