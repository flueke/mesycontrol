#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
from functools import partial
from functools import wraps
import util
import weakref

import application_registry
import app_model
import command
import config_loader
import hw_model
import mrc_command
import mrc_connection
import mrc_controller

def makes_dirty(f):
    """Method decorator which executes `wrapped_object.set_dirty()' after
    successful method invokation."""
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        ret = f(self, *args, **kwargs)
        self.set_dirty()
        return ret
    return wrapper

class ConfigError(Exception):
    pass

class ConfigObject(QtCore.QObject):
    dirty_changed         = pyqtSignal(bool)
    name_changed          = pyqtSignal(str)
    description_changed   = pyqtSignal(str)

    def __init__(self, parent=None):
        super(ConfigObject, self).__init__(parent)
        self._name        = None
        self._description = None
        self._dirty       = False

    def get_name(self):
        return self._name if self._name is not None else str()

    @makes_dirty
    def set_name(self, name):
        self._name = str(name) if name is not None else None
        self.name_changed.emit(self.name)

    def get_description(self):
        return self._description if self._description is not None else str()

    @makes_dirty
    def set_description(self, description):
        self._description = str(description) if description is not None else None
        self.description_changed.emit(self.name)

    def set_dirty(self):
        self._dirty = True
        self.dirty_changed.emit(self.is_dirty())

    def is_dirty(self):
        return self._dirty

    def clear_dirty(self):
        self._dirty = False
        self.dirty_changed.emit(self.is_dirty())

    name        = pyqtProperty(str, get_name, set_name, notify=name_changed)
    description = pyqtProperty(str, get_description, set_description, notify=description_changed)

class DeviceConfig(ConfigObject):
    idc_changed             = pyqtSignal(int)
    bus_changed             = pyqtSignal(int)
    address_changed         = pyqtSignal(int)
    rc_changed              = pyqtSignal(bool)
    parameter_added         = pyqtSignal(int)       #: address
    parameter_removed       = pyqtSignal(int)       #: address
    parameter_value_changed = pyqtSignal(int, int)  #: address, value
    parameter_alias_changed = pyqtSignal(int, str)  #: address, alias

    def __init__(self, parent=None):
        super(DeviceConfig, self).__init__(parent)
        self._idc        = None
        self._bus        = None
        self._address    = None
        self._rc         = None
        self._parameters = dict()

    def get_idc(self):
        return self._idc

    @makes_dirty
    def set_idc(self, idc):
        self._idc = int(idc)
        self.idc_changed.emit(self.idc)

    def get_bus(self):
        return self._bus

    @makes_dirty
    def set_bus(self, bus):
        self._bus = int(bus)
        self.bus_changed.emit(self.bus)

    def get_address(self):
        return self._address

    @makes_dirty
    def set_address(self, address):
        self._address = int(address)
        self.address_changed.emit(self.address)

    def get_rc(self):
        return self._rc

    @makes_dirty
    def set_rc(self, rc):
        self._rc = bool(rc)
        self.rc_changed.emit(self.rc)

    def contains_parameter(self, address):
        return address in self._parameters

    def add_parameter(self, address, value=None, alias=None):
        if self.contains_parameter(address):
            raise ConfigError("Duplicate parameter address %d" % address)

        param_config = ParameterConfig(address, value, alias)

        self.add_parameter_config(param_config)

    @makes_dirty
    def add_parameter_config(self, param_config):
        if self.contains_parameter(param_config.address):
            raise ConfigError("Duplicate parameter address %d" % param_config.address)

        self._parameters[param_config.address] = param_config
        param_config.value_changed.connect(partial(self._on_parameter_value_changed,
            address=param_config.address))
        param_config.alias_changed.connect(partial(self._on_parameter_alias_changed,
            address=param_config.address))
        self.parameter_added.emit(param_config.address)

    @makes_dirty
    def remove_parameter(self, address):
        if not self.contains_parameter(address):
            raise ConfigError("Address %d not present in DeviceConfig" % address)
        del self._parameters[address]
        self.parameter_removed.emit(address)

    def get_parameter(self, address):
        return self._parameters[address]

    def get_parameters(self):
        return sorted(self._parameters.values(), key=lambda cfg: cfg.address)

    def set_parameter_value(self, address, value):
        if self.contains_parameter(address):
            self._parameters[address]['value'] = int(value) if value is not None else None
            self.parameter_value_changed.emit(address, self.get_parameter_value(address))
        else:
            self.add_parameter(address, value)

    def get_parameter_value(self, address):
        if not self.contains_parameter(address):
            raise ConfigError("Address %d not present in DeviceConfig" % address)
        return self.get_parameter_dict()['value']

    def set_parameter_alias(self, address, alias):
        if self.contains_parameter(address):
            self._parameters[address]['alias'] = str(alias) if alias is not None else None
            self.parameter_alias_changed.emit(address, self.get_parameter_alias(address))
        else:
            self.add_parameter(address, alias=alias)

    def get_parameter_alias(self, address):
        if not self.contains_parameter(address):
            raise ConfigError("Address %d not present in DeviceConfig" % address)
        return self.get_parameter_dict()['alias']

    def _on_parameter_value_changed(self, value, address):
        self.parameter_value_changed.emit(address, value)

    def _on_parameter_alias_changed(self, alias, address):
        self.parameter_alias_changed.emit(address, alias)

    def __str__(self):
        return "DeviceConfig(name=%s, idc=%d, bus=%d, address=%d, %d parameters" % (
                self.name, self.idc, self.bus, self.address, len(self.get_parameters()))

    idc     = pyqtProperty(int, get_idc, set_idc, notify=idc_changed)
    bus     = pyqtProperty(int, get_bus, set_bus, notify=bus_changed)
    address = pyqtProperty(int, get_address, set_address, notify=address_changed)
    rc      = pyqtProperty(bool, get_rc, set_rc, notify=rc_changed)

class MRCConfig(ConfigObject):
    device_config_added   = pyqtSignal(object)  #: DeviceConfig
    device_config_removed = pyqtSignal(object)  #: DeviceConfig
    connection_config_set = pyqtSignal(object)
    setup_changed         = pyqtSignal(object)

    def __init__(self, parent=None):
        super(MRCConfig, self).__init__(parent)
        self._connection_config = None
        self._device_configs = list()

    def add_device_config(self, device_config):
        if self.has_device_config(device_config.bus, device_config.address):
            raise RuntimeError("DeviceConfig exists (bus=%d, address=%d)" %
                    (device_config.bus, device_config.address))

        device_config.setParent(self)
        self._device_configs.append(device_config)
        self.device_config_added.emit(device_config)

    def remove_device_config(self, device_config):
        self._device_configs.remove(device_config)
        device_config.setParent(None)
        self.device_config_removed.emit(device_config)

    def get_device_config(self, bus, address):
        try:
            return filter(lambda cfg: cfg.bus == bus and cfg.address == address,
                    self._device_configs)[0]
        except IndexError:
            raise KeyError("No device config for bus=%d, address=%d" % (bus, address))

    def get_device_configs(self, bus=None):
        if bus is None:
            return list(self._device_configs)
        return filter(lambda cfg: cfg.bus == bus, self._device_configs)

    def has_device_config(self, bus, address):
        try:
            self.get_device_config(bus, address)
            return True
        except KeyError:
            return False

    def set_connection_config(self, connection_config):
        self._connection_config = connection_config
        self.connection_config_set.emit(connection_config)

    def get_connection_config(self):
        return self._connection_config

    def get_setup(self):
        return self._setup() if self._setup is not None else None

    def set_setup(self, setup):
        changed = self.setup is not setup
        self._setup = weakref.ref(setup) if setup is not None else None
        if changed:
            self.setup_changed.emit(self.setup)

    def __str__(self):
        return "MRCConfig(name=%s, connection=%s, %d device configs)" % (
                self.name, self.connection_config.get_connection_info(), len(self.device_configs))

    device_configs    = pyqtProperty(list, get_device_configs)
    connection_config = pyqtProperty(object, get_connection_config, set_connection_config)
    setup             = pyqtProperty(object, set_setup, get_setup, notify=setup_changed)

class Setup(ConfigObject):
    device_config_added   = pyqtSignal(DeviceConfig)
    device_config_removed = pyqtSignal(DeviceConfig)
    mrc_config_added      = pyqtSignal(MRCConfig)
    mrc_config_removed    = pyqtSignal(MRCConfig)

    def __init__(self, parent=None):
        super(Setup, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self._mrc_configs    = list()
        self._device_configs = list()

    def add_device_config(self, device_config):
        """Add the given device config to this setup."""
        self.log.debug("adding %s", device_config)
        device_config.setParent(self)
        self._device_configs.append(device_config)
        self.device_config_added.emit(device_config)

    def remove_device_config(self, device_config):
        try:
            self._device_configs.remove(device_config)
            device_config.setParent(None)
            self.device_config_removed.emit(device_config)
            return True
        except ValueError:
            return False

    def get_device_configs(self):
        """Returns a list of the top level device configs in this setup.
        Note: This list does not contain the child device configs of this
        setups mrc configs.
        """
        return list(self._device_configs)

    def get_all_device_configs(self):
        """Returns a list of all device configs in this setup. The list
        contains both top-level configs and any device config children of the
        mrc configs contained in this setup.
        """
        ret = self.device_configs
        for mrc_cfg in self.mrc_configs:
            ret.extend(mrc_cfg.device_configs)

    def get_device_configs_by_idc(self, idc):
        return filter(lambda cfg: cfg.idc == idc, self._device_configs)

    def add_mrc_config(self, mrc_config):
        for mrc_cfg in self.mrc_configs:
            if mrc_cfg.connection_config.matches(mrc_config.connection_config):
                raise ConfigError("Request to add duplicate mrc connection to the setup (%s)"
                        % mrc_cfg.connection_config)

        mrc_config.setParent(self)
        self._mrc_configs.append(mrc_config)
        self.mrc_config_added.emit(mrc_config)

    def remove_mrc_config(self, mrc_config):
        try:
            self._mrc_configs.remove(mrc_config)
            mrc_config.setParent(None)
        except ValueError:
            return False
        self.mrc_config_removed.emit(mrc_config)
        return True

    def get_mrc_configs(self):
        """Returns a list of the MRC configs in this setup."""
        return list(self._mrc_configs)

    mrc_configs    = pyqtProperty(list, get_mrc_configs)
    device_configs = pyqtProperty(list, get_device_configs)

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

    def is_valid(self):
        """Returns true if a connection method has been set, false otherwise."""
        return (self.is_mesycontrol_connection()
                or self.is_serial_connection()
                or self.is_tcp_connection())

    def get_connection_info(self):
        if self.is_serial_connection():
            return "serial://%s@%d" % (self.serial_device, self.serial_baud_rate)
        if self.is_tcp_connection():
            return "tcp://%s:%d" % (self.tcp_host, self.tcp_port)
        if self.is_mesycontrol_connection():
            return "mesycontrol://%s:%d" % (self.mesycontrol_host, self.mesycontrol_port)

    def __str__(self):
        return "MRCConnectionConfig(%s)" % self.get_connection_info()

    def reset(self):
        self.reset_connection()

    def reset_connection(self):
        self._mesycontrol_host = None
        self._mesycontrol_port = None
        self._serial_device = None
        self._serial_baud_rate = None
        self._tcp_host = None
        self._tcp_port = None

    def set_mesycontrol_host(self, host):
        if self.is_valid() and not self.is_mesycontrol_connection():
            raise ConfigError("Cannot set mesycontrol_host on non-mesycontrol connection.")
        self._mesycontrol_host = str(host)

    def set_mesycontrol_port(self, port):
        if self.is_valid() and not self.is_mesycontrol_connection():
            raise ConfigError("Cannot set mesycontrol_port on non-mesycontrol connection.")
        self._mesycontrol_port = int(port)

    def set_serial_device(self, device):
        if self.is_valid() and not self.is_serial_connection():
            raise ConfigError("Cannot set serial_device on non-serial connection.")
        self._serial_device = str(device)

    def set_serial_baud_rate(self, baud):
        if self.is_valid() and not self.is_serial_connection():
            raise ConfigError("Cannot set serial_baud_rate on non-serial connection.")
        self._serial_baud_rate = int(baud)

    def set_tcp_host(self, host):
        if self.is_valid() and not self.is_tcp_connection():
            raise ConfigError("Cannot set tcp_host on non-tcp connection.")
        self._tcp_host = str(host)

    def set_tcp_port(self, port):
        if self.is_valid() and not self.is_tcp_connection():
            raise ConfigError("Cannot set tcp_port on non-tcp connection.")
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

    def matches(self, other):
        """Returns true if this config matches the connection config given in
        `other'. Matching means that both configs would connect to the same
        hardware."""
        if self.is_mesycontrol_connection() and other.is_mesycontrol_connection():
            return (self.mesycontrol_host == other.mesycontrol_host and
                    self.mesycontrol_port == other.mesycontrol_port)

        elif self.is_serial_connection() and other.is_serial_connection():
            # The baud rate is deliberately ignored here
            return (self.serial_device == other.serial_device)

        elif self.is_tcp_connection() and other.is_tcp_connection():
            return (self.tcp_host == other.tcp_host and
                    self.tcp_port == other.tcp_port)

        return False


    mesycontrol_host    = pyqtProperty(str, get_mesycontrol_host, set_mesycontrol_host)
    mesycontrol_port    = pyqtProperty(int, get_mesycontrol_port, set_mesycontrol_port)
    serial_device       = pyqtProperty(str, get_serial_device, set_serial_device)
    serial_baud_rate    = pyqtProperty(int, get_serial_baud_rate, set_serial_baud_rate)
    tcp_host            = pyqtProperty(str, get_tcp_host, set_tcp_host)
    tcp_port            = pyqtProperty(int, get_tcp_port, set_tcp_port)

class ParameterConfig(QtCore.QObject):
    value_changed = pyqtSignal(object) #: int value or None
    alias_changed = pyqtSignal(object) #: str value or None

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
        new_value = int(value) if value is not None else None
        if self.value != new_value:
            self._value = new_value
            self.value_changed.emit(self.value)

    def get_alias(self):
        return self._alias

    def set_alias(self, alias):
        new_alias = str(alias) if alias is not None else None
        if self.alias != new_alias:
            self._alias = new_alias
            self.alias_changed.emit(self.alias)

    #: Numeric parameter address.
    address = pyqtProperty(int, get_address)
    #: The parameters unsigned short value.
    value   = pyqtProperty(int, get_value, set_value)
    #: Optional user defined alias for the parameter.
    alias   = pyqtProperty(str, get_alias, set_alias)

def make_device_config(device):
    device_config = device.config
    if device_config is None:
        device_config         = DeviceConfig()
        device_config.idc     = device.idc
        device_config.bus     = device.bus
        device_config.address = device.address
        device_config.rc      = device.rc

    param_filter = lambda pd: not pd.read_only and not pd.do_not_store

    for param_profile in filter(param_filter, device.profile.parameters.values()):
        address = param_profile.address

        if not device.has_parameter(address):
            raise ConfigError("Required memory value not present", address)

        value = device.get_parameter(address)
        if not device_config.contains_parameter(address):
            device_config.add_parameter(address, value)
        else:
            device_config.get_parameter(address).value = value

    return device_config

def make_connection_config(connection):
    ret = MRCConnectionConfig()

    if type(connection) is mrc_connection.LocalMesycontrolConnection:
        server = connection.server
        if server.mrc_serial_port is not None:
            ret.serial_device    = server.mrc_serial_port
            ret.serial_baud_rate = server.mrc_baud_rate
        elif server.mrc_host is not None:
            ret.tcp_host = server.mrc_host
            ret.tcp_port = server.mrc_port
    elif type(connection) is mrc_connection.MesycontrolConnection:
        ret.mesycontrol_host = connection.host
        ret.mesycontrol_port = connection.port
    else:
        raise RuntimeError("Unhandled connection type %s" % type(connection).__name__)

    return ret

class SetupBuilder(command.SequentialCommandGroup):
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
            self.add(mrc_command.ReadParameter(device, param_description.address))

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

        ret = Setup()
        ret.connection_configs.extend(self._connection_configs.itervalues())
        ret.device_configs.extend(
                (make_device_config(device) for device in self._devices))

        return ret

class DeviceConfigBuilder(command.SequentialCommandGroup):
    def __init__(self, device, parent=None):
        super(DeviceConfigBuilder, self).__init__(parent)
        self.device = device

        param_filter = lambda pd: not pd.read_only and not pd.do_not_store
        required_parameters = filter(param_filter, device.description.parameters.values())

        for param_descr in required_parameters:
            if not device.has_parameter(param_descr.address):
                self.add(mrc_command.ReadParameter(device, param_descr.address))

    def get_result(self):
        if self.has_failed():
            return super(DeviceConfigBuilder, self).get_result()

        return make_device_config(self.device)

class DeviceConfigCompleter(command.SequentialCommandGroup):
    """Makes sure all parameters needed to complete this devices config are present.
    This command issues read requests for missing parameters. The device object
    will then automatically fill in missing config values.
    """
    def __init__(self, device, parent=None):
        super(DeviceConfigCompleter, self).__init__(parent)
        self.device = device

        param_filter = lambda pd: not pd.read_only and not pd.do_not_store
        required_parameters = filter(param_filter, device.description.parameters.values())

        for param_descr in required_parameters:
            if not device.config.contains_parameter(param_descr.address):
                if not device.has_parameter(param_descr.address):
                    self.add(mrc_command.ReadParameter(device, param_descr.address))

class SetupCompleter(command.SequentialCommandGroup):
    """Makes sure all required parameters for all connected devices in this setup are present.
    Uses DeviceConfigCompleter to complete individual device configurations.
    """
    def __init__(self, setup, parent=None):
        super(SetupCompleter, self).__init__(parent)
        self.setup = setup

        for mrc_config in setup.mrc_configs:
            mrc = application_registry.instance.find_mrc_by_config(mrc_config)

            if mrc is None:
                raise RuntimeError("No MRC found for MRC config: %s" % mrc_config)

            for device in mrc.get_devices():
                self.add(DeviceConfigCompleter(device))

#class DelayedConfigLoader(SequentialCommandGroup):
#    def __init__(self, mrc, device_config, device_description, verify=True, parent=None):
#        super(DelayedConfigLoader, self).__init__(parent)
#        self.mrc         = mrc
#        self.config      = device_config
#        self.description = device_description
#        self._verify     = verify
#
#    def _start(self):
#        try:
#            bus    = self.config.bus_number
#            dev    = self.config.device_address
#            device = self.mrc.device_models[bus][dev]
#        except KeyError:
#            raise RuntimeError("Device not found (bus=%d, dev=%d)" % (bus, dev))
#
#        if device.idc != self.config.device_idc:
#            raise RuntimeError("Device IDC mismatch (bus=%d, dev=%d, idc=%d, expected idc=%d)" %
#                    (bus, dev, device.idc, self.config.device_idc))
#
#        self.add(ConfigLoader(device, self.config, self.description))
#        if self._verify:
#            self.add(ConfigVerifier(device, self.config))
#
#        super(DelayedConfigLoader, self)._start()

#class SetupLoader(SequentialCommandGroup):
#    def __init__(self, config, parent=None):
#        super(SetupLoader, self).__init__(parent)
#        self._config = config
#        self._mrc_to_device_configs = dict()
#        self.app_model = application_registry.instance
#
#        for device_config in config.device_configs:
#            connection_name = device_config.connection_name
#            try:
#                connection = filter(lambda c: c.mrc.name == connection_name, self.app_model.mrc_connections)[0]
#            except IndexError:
#                try:
#                    # Find the connection config referenced by the device
#                    # config and use it to create a new connection.
#                    connection_config = filter(lambda cfg: cfg.name == connection_name, config.connection_configs)[0]
#                    connection = mrc_connection.factory(config=connection_config)
#                    self.app_model.registerConnection(connection)
#                except IndexError:
#                    raise RuntimeError("Connection not found: %s" % connection_name)
#
#            connection.sig_connection_error.connect(self._slt_connection_error)
#
#            if not connection.is_connected():
#                connection.connect()
#
#            mrc = connection.mrc_model
#
#            if mrc not in self._mrc_to_device_configs:
#                self._mrc_to_device_configs[mrc] = list()
#            self._mrc_to_device_configs[mrc].append(device_config)
#
#        for mrc in self._mrc_to_device_configs.keys():
#            for bus in range(2):
#                self.add(Scanbus(mrc, bus))
#
#        for mrc, cfgs in self._mrc_to_device_configs.iteritems():
#            for cfg in cfgs:
#                descr = self.app_model.get_device_description_by_idc(cfg.device_idc)
#                if descr is None:
#                    descr = device_description.makeGenericDescription(cfg.device_idc)
#                self.add(DelayedConfigLoader(mrc, cfg, descr))
#
#    def _slt_connection_error(self, error_object):
#        self._exception = error_object
#        self._stopped(False)

class SetupLoader(command.Command):
    """Loads the given setup.
    Steps:
        for each mrc not contained in the setup:
            disconnect and remove the mrc from the application

        for each mrc_config in setup.mrc_configs:
            if not application_registry.instance.find_mrc_by_config(mrc_config):
                create MRC and connect and set mrc_config
            else:
                set mrc_config
        wait until everything is connected and ready.
        for each device in the MRCs belonging to this setup:
            apply config to device
    """

    def __init__(self, setup, parent=None):
        super(SetupLoader, self).__init__(parent)
        self.setup = setup
        self.log   = util.make_logging_source_adapter(__name__, self)
        self._pending_mrcs = set()
        self._pending_config_loaders = set()

    def _start(self):
        self._failed = False
        registry = application_registry.instance
        registry.register('active_setup', self.setup)

        mrcs_to_remove = set(registry.get_mrcs())

        for mrc_config in self.setup.mrc_configs:
            mrc = registry.find_mrc_by_config(mrc_config)
            if mrc is not None:
                mrcs_to_remove.remove(mrc)

        for mrc in mrcs_to_remove:
            self.log.info("Removing MRC %s", mrc)
            mrc.disconnect()
            registry.unregister_mrc(mrc)

        for mrc_config in self.setup.mrc_configs:
            mrc = registry.find_mrc_by_config(mrc_config)
            if mrc is not None:
                self.log.info("Found MRC %s: applying config", mrc)
                mrc.config = mrc_config
                if not mrc.is_connected():
                    mrc.connect()
                    mrc.ready.connect(partial(self._on_mrc_ready, mrc=mrc))
                    mrc.disconnected.connect(partial(self._on_mrc_disconnected, mrc=mrc))
                else:
                    self._on_mrc_ready(mrc)
            else:
                connection = mrc_connection.factory(config=mrc_config.connection_config)
                mrc_model = hw_model.MRCModel()
                mrc_model.controller = mrc_controller.MesycontrolMRCController(connection, mrc_model)
                registry.register_mrc_model(mrc_model)
                mrc = app_model.MRC(mrc_model=mrc_model, mrc_config=mrc_config)
                registry.register_mrc(mrc)
                mrc.ready.connect(partial(self._on_mrc_ready, mrc=mrc))
                mrc.disconnected.connect(partial(self._on_mrc_disconnected, mrc=mrc))
                self._pending_mrcs.add(mrc)
                self.log.info("Created MRC %s", mrc)
                mrc.connect()

        self._completion_check()

    def _on_mrc_ready(self, mrc):
        self.log.info("MRC %s is ready. Loading configs")
        try:
            self._pending_mrcs.remove(mrc)
        except KeyError:
            pass

        for device_config in mrc.config.device_configs:
            device = mrc.get_device(device_config.bus, device_config.address)
            if not device.has_model():
                continue

            loader = config_loader.ConfigLoader(device, device_config)
            loader.stopped.connect(partial(self._on_config_loader_stopped, config_loader=loader))
            self._pending_config_loaders.add(loader)
            loader.start()

        self._completion_check()

    def _on_mrc_disconnected(self, mrc, info=None):
        try:
            self._pending_mrcs.remove(mrc)
        except KeyError:
            pass
        self._failed = True
        self._completion_check()

    def _on_config_loader_stopped(self, config_loader):
        try:
            self._pending_config_loaders.remove(config_loader)
        except KeyError:
            pass
        self._failed = config_loader.has_failed()
        self._completion_check()

    def _completion_check(self):
        if len(self._pending_mrcs) == 0 and len(self._pending_config_loaders) == 0:
            self._stopped(True)

    def _has_failed(self):
        return self._failed

    def _stop(self):
        for loader in self._pending_config_loaders:
            loader.stop()
        for mrc in self._pending_mrcs:
            mrc.disconnect()

    def _get_result(self):
        if not self.is_complete():
            return False
        return not self.has_failed()

#class SetupLoader(SequentialCommandGroup):
#    def __init__(self, setup, parent=None):
#        super(SetupLoader, self).__init__(parent)
#        self.setup = setup
#        self.registry = application_registry.instance

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

