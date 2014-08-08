#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal

from command import SequentialCommandGroup
from config_loader import ConfigLoader, ConfigVerifier
from mrc_command import ReadParameter, Scanbus
from mrc_connection import MesycontrolConnection, LocalMesycontrolConnection
import application_registry
import device_description
import mrc_connection

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

    def add_device_config(self, device_config):
        self._device_configs.append(device_config)

    def get_device_configs(self):
        return list(self._device_configs)

    def add_connection_config(self, mrc_config):
        self._mrc_configs.append(mrc_config)

    def get_connection_configs(self):
        return list(self._mrc_configs)

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
    name_changed             = pyqtSignal(object)
    bus_changed              = pyqtSignal(int)
    address_changed          = pyqtSignal(int)
    idc_changed              = pyqtSignal(int)
    rc_changed               = pyqtSignal(bool)
    parameter_changed        = pyqtSignal(int, int, int) #: address, old_value, new_value

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
        self._name = str(name) if name is not None else None
        self.name_changed.emit(self.name)

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

def make_device_config(device):
    device_config         = DeviceConfig(device.idc)
    device_config.name    = device.name
    device_config.bus     = device.bus
    device_config.address = device.address
    device_config.rc      = device.rc

    param_filter = lambda pd: not pd.read_only and not pd.do_not_store

    for param_description in filter(param_filter, device.description.parameters.values()):
        address = param_description.address

        if not device.has_parameter(address):
            raise DeviceConfigError("Required memory value not present", address)

        value = device.get_parameter(address)
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

class SetupBuilder(SequentialCommandGroup):
    def __init__(self, parent=None):
        super(SetupBuilder, self).__init__(parent)
        self._devices = set()
        self._connection_configs = dict()
        self.app_model = application_registry.instance

    def add_device(self, device):
        """Add a single device to the setup"""

        if device in self._devices: return

        self._devices.add(device)
        connection_config = make_connection_config(device.mrc_model.connection)
        self._connection_configs[connection_config.name] = connection_config
        device_descr = device.description

        param_filter = lambda pd: not pd.read_only and not pd.do_not_store

        for param_description in filter(param_filter, device_descr.parameters.values()):
            self.add(ReadParameter(device, param_description.address))

    def add_mrc(self, mrc):
        """Add all devices connected to the given MRC to the setup"""
        for bus, data in mrc.device_models.iteritems():
            for dev, device in data.iteritems():
                self.add_device(device)

    def get_result(self):
        if self.has_failed():
            return super(SetupBuilder, self).get_result()

        # All child commands completed without error. This means the device
        # models memory has been read and it's thus ok to call
        # make_device_config().

        ret = Config()
        ret.connection_configs.extend(self._connection_configs.itervalues())
        ret.device_configs.extend(
                (make_device_config(device) for device in self._devices))

        return ret

class DeviceConfigBuilder(SequentialCommandGroup):
    def __init__(self, device, parent=None):
        super(DeviceConfigBuilder, self).__init__(parent)
        self.device = device

        param_filter = lambda pd: not pd.read_only and not pd.do_not_store
        required_parameters = filter(param_filter, device.description.parameters.values())

        for param_descr in required_parameters:
            if not device.has_parameter(param_descr.address):
                self.add(ReadParameter(device, param_descr.address))

    def get_result(self):
        if self.has_failed():
            return super(DeviceConfigBuilder, self).get_result()

        return make_device_config(self.device)

class DelayedConfigLoader(SequentialCommandGroup):
    def __init__(self, mrc, device_config, device_description, verify=True, parent=None):
        super(DelayedConfigLoader, self).__init__(parent)
        self.mrc         = mrc
        self.config      = device_config
        self.description = device_description
        self._verify     = verify

    def _start(self):
        try:
            bus    = self.config.bus_number
            dev    = self.config.device_address
            device = self.mrc.device_models[bus][dev]
        except KeyError:
            raise RuntimeError("Device not found (bus=%d, dev=%d)" % (bus, dev))

        if device.idc != self.config.device_idc:
            raise RuntimeError("Device IDC mismatch (bus=%d, dev=%d, idc=%d, expected idc=%d)" %
                    (bus, dev, device.idc, self.config.device_idc))

        self.add(ConfigLoader(device, self.config, self.description))
        if self._verify:
            self.add(ConfigVerifier(device, self.config))

        super(DelayedConfigLoader, self)._start()

class SetupLoader(SequentialCommandGroup):
    def __init__(self, config, parent=None):
        super(SetupLoader, self).__init__(parent)
        self._config = config
        self._mrc_to_device_configs = dict()
        self.app_model = application_registry.instance

        for device_config in config.device_configs:
            connection_name = device_config.connection_name
            try:
                connection = filter(lambda c: c.mrc.name == connection_name, self.app_model.mrc_connections)[0]
            except IndexError:
                try:
                    # Find the connection config referenced by the device
                    # config and use it to create a new connection.
                    connection_config = filter(lambda cfg: cfg.name == connection_name, config.connection_configs)[0]
                    connection = mrc_connection.factory(config=connection_config)
                    self.app_model.registerConnection(connection)
                except IndexError:
                    raise RuntimeError("Connection not found: %s" % connection_name)

            connection.sig_connection_error.connect(self._slt_connection_error)

            if not connection.is_connected():
                connection.connect()

            mrc = connection.mrc_model

            if mrc not in self._mrc_to_device_configs:
                self._mrc_to_device_configs[mrc] = list()
            self._mrc_to_device_configs[mrc].append(device_config)

        for mrc in self._mrc_to_device_configs.keys():
            for bus in range(2):
                self.add(Scanbus(mrc, bus))

        for mrc, cfgs in self._mrc_to_device_configs.iteritems():
            for cfg in cfgs:
                descr = self.app_model.get_device_description_by_idc(cfg.device_idc)
                if descr is None:
                    descr = device_description.makeGenericDescription(cfg.device_idc)
                self.add(DelayedConfigLoader(mrc, cfg, descr))

    def _slt_connection_error(self, error_object):
        self._exception = error_object
        self._stopped(False)

# Operations:
# * Load Setup:
#   for each MRCConfig:
#     establish connection if needed
#     for each DeviceConfig:
#       load DeviceConfig (target mrc is the parent of the DeviceConfig)
#   result -> multiple (MRCConnection + MRCModel tree) objects

# * Load single MRCConfig from setup:
#   same as above but only the selected MRCConfig

# * Apply single MRCConfig to target mrc:
#   assert target exists and is ready
#   for each DeviceConfig:
#       load DeviceConfig (target mrc is the given target, not the DeviceConfigs parent!)

# * Apply single DeviceConfig to device:
#   assert target device exists and is ready
#   assert DeviceConfig.idc matches target idc
#   apply DeviceConfig to target

# * Diff current device states and Setup device states
#   for each MRCConfig:
#     establish connection if needed
#     for each DeviceConfig:
#       read target device parameters
#       diff the device memory and DeviceConfig contents {0: (0, 1), 1: (123,
#       None), ...} (None only if all params should be diffed and Setup does
#       not contain the param
#       store/return the diff somehow
#   Where are the diffs kept? Who updates them?

# => Setup: Load only (into the gui), Connect only, Connect and diff, Connect
# and load device configs, Connect and set meta information (device names and
# descriptions)
# => MRCConfig: as for Setup but an optional target MRC can be supplied (use
# case: one client runs the server, another clients wants to modify the setup
# -> it needs to connect to the first clients server address)
# Better long term solution: run the server standalone and change the
# MRCConfig.connection_config accordingly

# Change tracking:
# * Changes to parameter values, object names, descriptions and so on must be
#   tracked. The source Setup should be marked as modified. On close the user
#   must be asked if he wants to save the changes. It should be possible to
#   disable change tracking (i.e. close the source Setup but keep the connection open).
#   DeviceModel.name changes -> DeviceConfig.name must change too
# * The user must be able to add/remove MRCs and devices from/to a setup.
#   For now this could be implemented by creating a new setup containing the
#   desired devices and overwriting the old setup.
#   How does this work? We'd have two setups: the one that was originally
#   loaded and a new one reflecting the user-made changes.
# * Model tree <-> observer <-> Setup tree

# Complicated case:
# A Setup has been successfully loaded.
# A single DeviceConfig is applied to a device that's also contained in the Setup.
# Should the device be removed from the setup? Should the new DeviceConfig
# replace the existing config in the setup? => Replace is probably better. The
# original Setup gets modified, the newly loaded DeviceConfig is not modified.

# Complicated case 2:
# A setup has been successfully loaded.
# The user wants to load and apply a different setup.
# The new setup must replace the old setup. The old setup should be closed and
# changes be written to disk if desired.
# How to handle a device that was present in the old setup but is not present
# in the new setup? It's not modified by loading the setup but it also is not
# contained in the setup so it will not be saved. The user must be able to mark
# the device to be included in the setup. => Device selection needed.

# Error handling and reporting when loading setups:
# * Errors: connection failed (timeout, server error, ...), device not found,
#   device idc mismatch, read/write error, permission denied (needs write
#   access), verification error (if verification is enabled).
#   The above errors are easy to catch and report. By default SetupLoader
#   quits after the first error it encounters. This means the setup may have
#   been partially loaded.
#   => Report the error via popup and in the logs and be done with it.

#class Setup(util.NamedObject):
#    def __init__(self, parent=None):
#        super(Setup, self).__init__(parent=parent)
#        self.description = None
#        self.mrc_configs = []
#
#class MRCConfig(util.NamedObject):
#    def __init__(self, parent=None):
#        super(MRCConfig, self).__init__(parent=parent)
#        self.description        = None
#        self.connection_config  = None
#        self.device_configs     = []
#
#class ConnectionConfig(util.NamedObject):
#    def __init__(self, parent=None):
#        super(ConnectionConfig, self).__init__(parent=parent)
#        self.mesycontrol_host    = None
#        self.mesycontrol_port    = None
#        self.serial_device       = None
#        self.serial_baud_rate    = None
#        self.tcp_host            = None
#        self.tcp_port            = None
#        self.listen_address      = None
#        self.listen_port         = None
#
#class DeviceConfig(util.NamedObject):
#    def __init__(self, parent=None):
#        super(DeviceConfig, self).__init__(parent=parent)
#        self.description    = None
#        self.idc            = None
#        self.bus            = None
#        self.dev            = None
#        self.parameters     = []
#
#class ParameterConfig(util.NamedObject):
#    def __init__(self, parent=None):
#        super(ParameterConfig, self).__init__(parent=parent)
#        self.address = None
#        self.value   = None


#class SetupBuilder(SequentialCommandGroup):
#    def __init__(self, parent=None):
#        super(SetupBuilder, self).__init__(parent)
#        self.result = Setup()
#
#    def add_mrc(self, mrc):
#        mrc_config = make_mrc_config(mrc)
#        for device in mrc.get_devices():
#            mrc_config.device_configs.append(make_device_config(device))
#        self.mrc_configs.append(mrc_config)
#
#    def add_device(self, device):

