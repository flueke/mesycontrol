#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal

import util
import device_description
from mrc_connection import MesycontrolConnection, LocalMesycontrolConnection

#def observe_property_change(prop_name):
#    def the_decorator(method):
#        def inner(self, *args, **kwargs):
#            old_prop_value = getattr(self, prop_name)
#            method(self, *args, **kwargs)
#            new_prop_value = getattr(self, prop_name)
#            if old_prop_value != new_prop_value:
#                print "emitting!"
#                self.changed.emit()
#        return inner
#    return the_decorator
#
#    @observe_property_change('name')
#    def set_name(self, name):
#        self._name = name

class Config(QtCore.QObject):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super(Config, self).__init__(parent)
        self._name           = None
        self._description    = None
        self._mrc_configs    = list()
        self._device_configs = list()

    def get_name(self):
        return self._name if self._name is not None else str()

    def set_name(self, name):
        old_value = self.name
        self._name = str(name) if name is not None else None
        if self.name != old_value:
            self.changed.emit()

    name = pyqtProperty(str, get_name, set_name)

class MRCConnectionConfigError(Exception):
    pass

class MRCConnectionConfig(QtCore.QObject):
    """MRC connection configuration. Possible connection types are serial, tcp
    and mesycontrol_server."""

    def __init__(self, parent=None):
        super(MRCConnectionConfig, self).__init__(parent)
        self.reset()

    def is_mesycontrol_connection(self):
        return self.mesycontrol_host is not None and self.mesycontrol_port is not None

    def is_serial_connection(self):
        return self.serial_device is not None and self.serial_baud_rate is not None

    def is_tcp_connection(self):
        return self.tcp_host is not None and self.tcp_port is not None

    def is_local_connection(self):
        return self.is_serial_connection() or self.is_tcp_connection()

    def is_connection_valid(self):
        """Returns true if a connection method has been set, false otherwise."""
        return (self.is_mesycontrol_connection()
                or self.is_serial_connection()
                or self.is_tcp_connection())

    def is_valid(self):
        """Returns true if a connection method and a name have been set."""
        return (self.name is not None
                and self.is_connection_valid())

    def get_connection_info(self):
        if self.is_serial_connection():
            return "serial://%s@%d" % (self.serial_device, self.serial_baud_rate)
        if self.is_tcp_connection():
            return "tcp://%s:%d" % (self.tcp_host, self.tcp_port)
        if self.is_mesycontrol_connection():
            return "mesycontrol://%s:%d" % (self.mesycontrol_host, self.mesycontrol_port)

    def reset(self):
        self._name = None
        self.reset_connection()

    def reset_connection(self):
        self._mesycontrol_host = None
        self._mesycontrol_port = None
        self._serial_device = None
        self._serial_baud_rate = None
        self._tcp_host = None
        self._tcp_port = None

    def set_name(self, name):
        self._name = str(name)

    def get_name(self):
        return self._name

    def set_mesycontrol_host(self, host):
        if self.is_connection_valid() and not self.is_mesycontrol_connection():
            raise MRCConnectionConfigError("Cannot set mesycontrol_host on non-mesycontrol connection.")
        self._mesycontrol_host = str(host)

    def set_mesycontrol_port(self, port):
        if self.is_connection_valid() and not self.is_mesycontrol_connection():
            raise MRCConnectionConfigError("Cannot set mesycontrol_port on non-mesycontrol connection.")
        self._mesycontrol_port = int(port)

    def set_serial_device(self, device):
        if self.is_connection_valid() and not self.is_serial_connection():
            raise MRCConnectionConfigError("Cannot set serial_device on non-serial connection.")
        self._serial_device = str(device)

    def set_serial_baud_rate(self, baud):
        if self.is_connection_valid() and not self.is_serial_connection():
            raise MRCConnectionConfigError("Cannot set serial_baud_rate on non-serial connection.")
        self._serial_baud_rate = int(baud)

    def set_tcp_host(self, host):
        if self.is_connection_valid() and not self.is_tcp_connection():
            raise MRCConnectionConfigError("Cannot set tcp_host on non-tcp connection.")
        self._tcp_host = str(host)

    def set_tcp_port(self, port):
        if self.is_connection_valid() and not self.is_tcp_connection():
            raise MRCConnectionConfigError("Cannot set tcp_port on non-tcp connection.")
        self._tcp_port = int(port)

    def get_mesycontrol_host(self):
        return self._mesycontrol_host

    def get_mesycontrol_port(self):
        return self._mesycontrol_port

    def get_serial_device(self):
        return self._serial_device

    def get_serial_baud_rate(self):
        return self._serial_baud_rate

    def get_tcp_host(self):
        return self._tcp_host

    def get_tcp_port(self):
        return self._tcp_port

    def get_server_options(self):
        if self.is_serial_connection():
            return {'mrc_serial_port': self.get_serial_device(),
                    'mrc_baud_rate':   self.get_serial_baud_rate()}

        elif self.is_tcp_connection():
            return {'mrc_host': self.get_tcp_host(),
                    'mrc_port': self.get_tcp_port()}

        return None

    name                = pyqtProperty(str, get_name, set_name)
    mesycontrol_host    = pyqtProperty(str, get_mesycontrol_host, set_mesycontrol_host)
    mesycontrol_port    = pyqtProperty(int, get_mesycontrol_port, set_mesycontrol_port)
    serial_device       = pyqtProperty(str, get_serial_device, set_serial_device)
    serial_baud_rate    = pyqtProperty(int, get_serial_baud_rate, set_serial_baud_rate)
    tcp_host            = pyqtProperty(str, get_tcp_host, set_tcp_host)
    tcp_port            = pyqtProperty(int, get_tcp_port, set_tcp_port)

class DeviceConfigError(Exception):
    pass

class DeviceConfig(QtCore.QObject):
    """Mesytec device configuration containing ParameterConfig instances.
    Optionally an MRCConnectionConfig name, bus and device numbers may be
    specified."""

    changed = pyqtSignal()

    def __init__(self, device_idc, parent=None):
        super(DeviceConfig, self).__init__(parent)
        self._idc        = None
        self._bus        = None
        self._address    = None
        self._rc         = None
        self._name       = None
        self._parameters = list()

        self.idc = device_idc

    def get_name(self):
        return self._name

    def set_name(self, name):
        changed = self.name != str(name)
        self._name = str(name)
        if changed:
            self.changed.emit()

    def get_idc(self):
        return self._idc

    def set_idc(self, idc):
        changed = self.idc != int(idc)
        self._idc = int(idc)
        if changed:
            self.changed.emit()

    def get_bus(self):
        return self._bus

    def set_bus(self, bus):
        changed = self.bus != int(bus)
        self._bus = int(bus)
        if changed:
            self.changed.emit()

    def get_address(self):
        return self._address

    def set_address(self, address):
        changed = self.address != int(address)
        self._address = int(address)
        if changed:
            self.changed.emit()

    def get_rc(self):
        return self._rc

    def set_rc(self, rc):
        changed = self.rc != bool(rc)
        self._rc = bool(rc)
        if changed:
            self.changed.emit()

    def contains_parameter(self, address):
        return any(address == p.address for p in self._parameters)

    def add_parameter(self, parameter):
        if self.contains_parameter(parameter.address):
            raise DeviceConfigError("Duplicate parameter address %d" % parameter.address)

        parameter.setParent(self)
        self._parameters.append(parameter)
        self.changed.emit()

    def del_parameter(self, parameter):
        if parameter in self._parameters:
            self._parameters.remove(parameter)
            parameter.setParent(None)
            self.changed.emit()

    def get_parameter(self, address):
        try:
            return filter(lambda p: p.address == address, self._parameters)[0]
        except IndexError:
            return None

    def get_parameters(self):
        return list(self._parameters)

    idc     = pyqtProperty(int,  get_idc, set_idc)
    bus     = pyqtProperty(int,  get_bus, set_bus)
    address = pyqtProperty(int,  get_address, set_address)
    rc      = pyqtProperty(bool, get_rc, set_rc)
    name    = pyqtProperty(str,  get_name, set_name)

class ParameterConfig(QtCore.QObject):
    changed = pyqtSignal()

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
        changed = self.value != int(value)
        self._value = int(value)
        if changed:
            self.changed.emit()

    def get_alias(self):
        return self._alias

    def set_alias(self, alias):
        changed = self._alias != str(alias)
        self._alias = str(alias)
        if changed:
            self.changed.emit()

    #: Numeric parameter address.
    address = pyqtProperty(int, get_address)
    #: The parameters unsigned short value.
    value   = pyqtProperty(int, get_value, set_value)
    #: Optional user defined alias for the parameter.
    alias   = pyqtProperty(str, get_alias, set_alias)

def make_device_config(device_model, device_descr=None):
    device_config         = DeviceConfig(device_model.idc)
    device_config.bus     = device_model.bus
    device_config.address = device_model.address
    device_config.rc      = device_model.rc

    param_filter = lambda pd: not pd.read_only and not pd.do_not_store

    if device_descr is None:
        device_descr = device_description.make_generic_description()

    for param_description in filter(param_filter, device_descr.parameters.values()):
        address = param_description.address

        if not device_model.has_parameter(address):
            raise DeviceConfigError("Required memory value not present", address=address)

        value = device_model.get_parameter(address)
        device_config.add_parameter(ParameterConfig(address, value))

    return device_config

def make_connection_config(connection):
    ret = MRCConnectionConfig()

    if type(connection) is LocalMesycontrolConnection:
        server = connection.server
        if server.mrc_serial_port is not None:
            ret.serial_device    = server.mrc_serial_port
            ret.serial_baud_rate = server.mrc_baud_rate
        elif server.mrc_host is not None:
            ret.tcp_host = server.mrc_host
            ret.tcp_port = server.mrc_port
    elif type(connection) is MesycontrolConnection:
        ret.mesycontrol_host = connection.host
        ret.mesycontrol_port = connection.port
    else:
        raise RuntimeError("Unhandled connection type %s" % type(connection).__name__)

    return ret
