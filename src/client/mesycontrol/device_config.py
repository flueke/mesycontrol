#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal

class DeviceConfigError(Exception):
    pass

class DeviceConfig(QtCore.QObject):
    def __init__(self, parent=None):
        super(DeviceConfig, self).__init__(parent)
        self._device_description = None
        self._alias              = None
        self._mrc_address        = None
        self._mesycontrol_server = None
        self._bus_number         = None
        self._device_number      = None
        self._parameters         = []
        self._address2param      = {}

    def get_device_description(self):
        return self._device_description

    def set_device_description(self, obj):
        self._device_description = obj
        self.device_description_changed.emit(obj)

    def get_alias(self):
        return self._alias

    def set_alias(self, alias):
        self._alias = alias
        if alias is not None:
           self.alias_changed.emit(alias)

    def get_mrc_address(self):
        return self._mrc_address

    def set_mrc_address(self, address):
        self._mrc_address = address
        if address is not None:
           self.mrc_address_changed.emit(address)

    def get_mesycontrol_server(self):
        return self._mesycontrol_server

    def set_mesycontrol_server(self, server):
        self._mesycontrol_server = server
        if server is not None:
           self.mesycontrol_server_changed.emit(server)

    def get_bus_number(self):
        return self._bus_number

    def set_bus_number(self, bus_number):
        self._bus_number = bus_number
        if bus_number is not None:
           self._bus_number = int(bus_number)
           self.bus_number_changed.emit(self.bus_number)

    def get_device_number(self):
        return self._device_number

    def set_device_number(self, device_number):
        self._device_number = device_number
        if device_number is not None:
           self._device_number = int(device_number)
           self.device_number_changed.emit(self.device_number)

    def add_parameter(self, parameter):
        if parameter.address in self._address2param:
            raise DeviceConfigError("Duplicate parameter address %d" % parameter.address)

        parameter.setParent(self)
        self._parameters.append(parameter)
        self._address2param[parameter.address] = parameter
        self.parameter_added.emit(parameter)

    def del_parameter(self, parameter):
        if parameter in self._parameters:
            self._parameters.remove(parameter)
            del self._address2param[parameter.address]
            parameter.setParent(None)
            self.parameter_deleted.emit(parameter)

    def get_parameter(self, address):
        return self._address2param.get(address, None)

    def get_parameters(self):
        return list(self._parameters)

    device_description_changed  = pyqtSignal(object)
    alias_changed               = pyqtSignal(object)
    mrc_address_changed         = pyqtSignal(str)
    mesycontrol_server_changed  = pyqtSignal(str)
    bus_number_changed          = pyqtSignal(int)
    device_number_changed       = pyqtSignal(int)
    parameter_added             = pyqtSignal(object)
    parameter_deleted           = pyqtSignal(object)

    #: Optional name of a device description or a DeviceDescription instance or None.
    device_description = pyqtProperty(object,
            get_device_description, set_device_description, notify=device_description_changed)

    #: Optional user defined alias for this device.
    alias = pyqtProperty(str, get_alias, set_alias, notify=alias_changed)

    #: Optional mrc address specification.
    #: Format is: <dev>@<baud> or <host>:<port>.
    #: If specified this setting can enable auto-starting of a mesycontrol
    #: server connecting to the given mrc.
    mrc_address = pyqtProperty(str, get_mrc_address, set_mrc_address, notify=mrc_address_changed)

    #: Optional address of a mesycontrol server to connect to.
    #: Format is <host>:<port>.
    mesycontrol_server = pyqtProperty(str, get_mesycontrol_server, set_mesycontrol_server,
            notify=mesycontrol_server_changed)

    #: Optional bus number of the device.
    bus_number = pyqtProperty(int, get_bus_number, set_bus_number, notify=bus_number_changed)

    #: Optional device number on the bus.
    device_number = pyqtProperty(int, get_device_number, set_device_number, notify=device_number_changed)

class ParameterConfig(QtCore.QObject):
    def __init__(self, address, value=None, alias=None, parent=None):
        super(ParameterConfig, self).__init__(parent)
        self._address = int(address)
        self._value   = int(value) if value is not None else None
        self._alias   = str(alias) if alias is not None else None

    def get_address(self):
        return self._address

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = int(value) if value is not None else None
        if self._value is not None:
           self.value_changed.emit(self._value)

    def get_alias(self):
        return self._alias

    def set_alias(self, alias):
        self._alias = str(alias) if alias is not None else None
        if self._alias is not None:
           self.alias_changed.emit(self._alias)

    value_changed = pyqtSignal(int)
    alias_changed = pyqtSignal(str)

    #: Numeric address or parameter description name
    address = pyqtProperty(int, get_address)
    #: The parameters unsigned short value.
    value   = pyqtProperty(int, get_value, set_value, notify=value_changed)
    #: Optional user defined alias for the parameter.
    alias   = pyqtProperty(str, get_alias, set_alias, notify=alias_changed)

# Where to store aliases for MRCs? Probably in the clients connection list.
# Then MRC aliases could be used in device configurations instead of some kind
# of address specification (e.g. device config references "my_mrc1" and the
# client contains a mrc connection with that name => mrc name from config can
# be resolved). The mrc connection list should also be exportable!

# Mesycontrol (XML) file contents:
# * Zero or more device descriptions
# * Zero or more device configurations
# * At least one of the above must be present
# * An optional file description/comment.
# * The device configurations may reference file-internal device descriptions,
#   built-in device descriptions and possibly filenames containing device
#   descriptions.
#
# * A device configuration may include an mrc identifier plus bus and device
#   numbers (basically a full device address) to enable automatic loading of a
#   setup. If no device address is given the user must be asked for one.
#   Using the full device address together with device descriptions enables
#   verifying of device IDCs when loading a configuration (is the device
#   present? does it have the correct IDC?)
# * Loading of a device configuration:
#   Parameters are written to the device in the order they're declared in the
#   description file. If no description is present (just raw param -> value
#   entries in the config) the order of parameters is used instead.
#   TODO (later): How to specify a load order for generic devices when
#   creating a generic device description via the generic device widget? For
#   now the file could just be hand-edited.
# * TODO: How to test for certain firmware versions? E.g. MSCF16 submodels?
# * IDC is the same but the contents of a certain parameter (the firmware
#   revision) differ.
#   Two scenarios for this:
#     - Use a single device description with submodel specific parameters.
#     - Write multiple device descriptions with each one specifying which
#       firmware revision it expects.
