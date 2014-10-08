#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
from functools import partial
from functools import wraps

import application_registry
import command
import config_loader
import mrc_command
import mrc_connection
import util

def modifies(f):
    """Method decorator which executes `wrapped_object.set_modified(True)'
    after successful method invokation."""
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        ret = f(self, *args, **kwargs)
        self.set_modified(True)
        return ret
    return wrapper

class ConfigError(Exception):
    pass

class ConfigObject(QtCore.QObject):
    modified_changed    = pyqtSignal(bool)
    name_changed        = pyqtSignal(object)
    description_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super(ConfigObject, self).__init__(parent)
        self._name          = None
        self._description   = None
        self._modified      = False

    def get_name(self):
        return self._name if self._name is not None else str()

    @modifies
    def set_name(self, name):
        self._name = str(name) if name is not None else None
        self.name_changed.emit(self.name)

    def get_description(self):
        return self._description if self._description is not None else str()

    @modifies
    def set_description(self, description):
        self._description = str(description) if description is not None else None
        self.description_changed.emit(self.name)

    def set_modified(self, m):
        self._modified = bool(m)
        self._set_modified(m)
        self.modified_changed.emit(self.is_modified())

    def is_modified(self):
        return self._modified

    def _set_modified(self, m):
        """set_modified hook to implement custom behaviour in subclasses"""
        pass

    name        = pyqtProperty(str, get_name, set_name, notify=name_changed)
    description = pyqtProperty(str, get_description, set_description, notify=description_changed)
    modified    = pyqtProperty(bool, is_modified, set_modified, notify=modified_changed)

class ParameterConfig(ConfigObject):
    value_changed = pyqtSignal(object) #: int value or None
    alias_changed = pyqtSignal(object) #: str value or None

    def __init__(self, address, value=None, alias=None, parent=None):
        super(ParameterConfig, self).__init__(parent)
        self._address = int(address)
        self._value   = int(value) if value is not None else None
        self._alias   = str(alias) if alias is not None else None

        self.value_changed.connect(self._on_property_changed)
        self.alias_changed.connect(self._on_property_changed)

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

    @modifies
    def _on_property_changed(self, alias):
        pass

    #: Numeric parameter address.
    address = pyqtProperty(int, get_address)
    #: The parameters unsigned short value (int or None)
    value   = pyqtProperty(object, get_value, set_value, notify=value_changed)
    #: Optional user defined alias for the parameter (str or None)
    alias   = pyqtProperty(object, get_alias, set_alias, notify=alias_changed)

class DeviceConfig(ConfigObject):
    idc_changed             = pyqtSignal(int)
    bus_changed             = pyqtSignal(int)
    address_changed         = pyqtSignal(int)
    rc_changed              = pyqtSignal(bool)
    parameter_added         = pyqtSignal([int], [ParameterConfig])       #: [address], [ParameterConfig]
    parameter_removed       = pyqtSignal([int], [ParameterConfig])       #: [address], [ParameterConfig]
    parameter_value_changed = pyqtSignal([int, object], [ParameterConfig])  #: [address, value], [ParameterConfig]
    parameter_alias_changed = pyqtSignal([int, object], [ParameterConfig])  #: [address, alias], [ParameterConfig]

    def __init__(self, parent=None):
        super(DeviceConfig, self).__init__(parent)
        self._idc        = None
        self._bus        = None
        self._address    = None
        self._rc         = None
        self._parameters = dict()

    def get_idc(self):
        return self._idc

    @modifies
    def set_idc(self, idc):
        self._idc = int(idc)
        self.idc_changed.emit(self.idc)

    def get_bus(self):
        return self._bus

    @modifies
    def set_bus(self, bus):
        self._bus = int(bus)
        self.bus_changed.emit(self.bus)

    def get_address(self):
        return self._address

    @modifies
    def set_address(self, address):
        self._address = int(address)
        self.address_changed.emit(self.address)

    def get_rc(self):
        return self._rc

    @modifies
    def set_rc(self, rc):
        self._rc = bool(rc)
        self.rc_changed.emit(self.rc)

    def contains_parameter(self, address):
        return address in self._parameters

    @modifies
    def add_parameter(self, address, value=None, alias=None):
        if self.contains_parameter(address):
            raise ConfigError("Duplicate parameter address %d" % address)

        param_config = ParameterConfig(address, value, alias)

        self.add_parameter_config(param_config)

    @modifies
    def add_parameter_config(self, param_config):
        if self.contains_parameter(param_config.address):
            raise ConfigError("Duplicate parameter address %d" % param_config.address)

        self._parameters[param_config.address] = param_config

        param_config.modified_changed.connect(self._on_param_config_modified)
        param_config.value_changed.connect(partial(self._on_parameter_value_changed))
        param_config.alias_changed.connect(partial(self._on_parameter_alias_changed))

        self.parameter_added[int].emit(param_config.address)
        self.parameter_added[ParameterConfig].emit(param_config)

    @modifies
    def remove_parameter(self, address):
        if not self.contains_parameter(address):
            raise ConfigError("Address %d not present in DeviceConfig" % address)

        param_config = self._parameters[address]
        del self._parameters[address]
        param_config.modified_changed.disconnect(self._on_param_config_modified)

        self.parameter_removed[int].emit(address)
        self.parameter_removed[ParameterConfig].emit(param_config)

    def get_parameter(self, address):
        try:
            return self._parameters[address]
        except KeyError:
            raise ConfigError("Address %d not present in DeviceConfig" % address)

    def get_parameters(self):
        return sorted(self._parameters.values(), key=lambda cfg: cfg.address)

    def set_parameter_value(self, address, value):
        if self.contains_parameter(address):
            self.get_parameter(address).value = int(value) if value is not None else None
        else:
            self.add_parameter(address, value)

    def get_parameter_value(self, address):
        return self.get_parameter(address).value

    def set_parameter_alias(self, address, alias):
        if self.contains_parameter(address):
            self.get_parameter(address).alias = str(alias) if alias is not None else None
        else:
            self.add_parameter(address, alias=alias)

    def get_parameter_alias(self, address):
        return self.get_parameter(address).alias

    def _on_param_config_modified(self, is_modified):
        if is_modified:
            self.modified = True

    def _on_parameter_value_changed(self, value):
        address = self.sender().address
        self.parameter_value_changed[int, object].emit(address, value)
        self.parameter_value_changed[ParameterConfig].emit(self.get_parameter(address))

    def _on_parameter_alias_changed(self, alias):
        address = self.sender().address
        self.parameter_alias_changed[int, object].emit(address, alias)
        self.parameter_alias_changed[ParameterConfig].emit(self.get_parameter(address))

    def __str__(self):
        return "DeviceConfig(name=%s, idc=%d, bus=%d, address=%d, %d parameters" % (
                self.name, self.idc, self.bus, self.address, len(self._parameters))

    def _set_modified(self, m):
        if not m:
            for p in self.parameters:
                p.modified = False

    idc         = pyqtProperty(int, get_idc, set_idc, notify=idc_changed)
    bus         = pyqtProperty(int, get_bus, set_bus, notify=bus_changed)
    address     = pyqtProperty(int, get_address, set_address, notify=address_changed)
    rc          = pyqtProperty(bool, get_rc, set_rc, notify=rc_changed)
    parameters  = pyqtProperty(list, get_parameters)

class MRCConfig(ConfigObject):
    device_config_added   = pyqtSignal(object)  #: DeviceConfig
    device_config_removed = pyqtSignal(object)  #: DeviceConfig
    connection_config_set = pyqtSignal(object)  #: ConnectionConfig

    def __init__(self, parent=None):
        super(MRCConfig, self).__init__(parent)
        self._connection_config = None
        self._device_configs = list()

    @modifies
    def add_device_config(self, device_config):
        if self.has_device_config(device_config.bus, device_config.address):
            raise RuntimeError("DeviceConfig exists (bus=%d, address=%d)" %
                    (device_config.bus, device_config.address))

        device_config.setParent(self)
        self._device_configs.append(device_config)
        device_config.modified_changed.connect(self._on_child_modified)
        self.device_config_added.emit(device_config)

    @modifies
    def remove_device_config(self, device_config):
        self._device_configs.remove(device_config)
        device_config.setParent(None)
        device_config.modified_changed.disconnect(self._on_child_modified)
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

    @modifies
    def set_connection_config(self, connection_config):
        if self._connection_config is not None:
            connection_config.modified_changed.disconnect(self._on_child_modified)

        self._connection_config = connection_config
        connection_config.modified_changed.connect(self._on_child_modified)
        self.connection_config_set.emit(connection_config)

    def get_connection_config(self):
        return self._connection_config

    def __str__(self):
        return "MRCConfig(name=%s, connection=%s, %d device configs)" % (
                self.name, self.connection_config.get_connection_info(), len(self.device_configs))

    def _on_child_modified(self, m):
        if m:
            self.modified = True

    def _set_modified(self, m):
        if not m:
            for cfg in self.device_configs:
                cfg.modified = False

            if self.connection_config is not None:
                self.connection_config.modified = False

    device_configs    = pyqtProperty(list, get_device_configs)
    connection_config = pyqtProperty(object, get_connection_config, set_connection_config)

class Setup(ConfigObject):
    device_config_added     = pyqtSignal(DeviceConfig)
    device_config_removed   = pyqtSignal(DeviceConfig)
    mrc_config_added        = pyqtSignal(MRCConfig)
    mrc_config_removed      = pyqtSignal(MRCConfig)
    filename_changed        = pyqtSignal(str)

    def __init__(self, parent=None):
        super(Setup, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self._mrc_configs    = list()
        self._device_configs = list()
        self._filename       = str()

    @modifies
    def add_device_config(self, device_config):
        """Add the given device config to this setup."""
        self.log.debug("adding %s", device_config)
        device_config.setParent(self)
        device_config.modified_changed.connect(self._on_child_modified)
        self._device_configs.append(device_config)
        self.device_config_added.emit(device_config)

    @modifies
    def remove_device_config(self, device_config):
        try:
            self._device_configs.remove(device_config)
            device_config.setParent(None)
            device_config.modified_changed.disconnect(self._on_child_modified)
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

    @modifies
    def add_mrc_config(self, mrc_config):
        for mrc_cfg in self.mrc_configs:
            if mrc_cfg.connection_config.matches(mrc_config.connection_config):
                self.log.error("Request to add duplicate mrc connection to the setup. new_cfg=%s, mrc_configs in setup=%s",
                        mrc_config, self.get_mrc_configs())
                raise ConfigError("Request to add duplicate mrc connection to the setup (%s)"
                        % mrc_cfg.connection_config)

        mrc_config.setParent(self)
        self._mrc_configs.append(mrc_config)
        mrc_config.modified_changed.connect(self._on_child_modified)
        self.mrc_config_added.emit(mrc_config)

    @modifies
    def remove_mrc_config(self, mrc_config):
        self.log.debug("Removing MRC config %s", mrc_config)
        self._mrc_configs.remove(mrc_config)
        mrc_config.setParent(None)
        mrc_config.modified_changed.disconnect(self._on_child_modified)
        self.mrc_config_removed.emit(mrc_config)
        self.log.debug("Removed MRC config %s. %d MRC configs left in setup.",
                mrc_config, len(self._mrc_configs))

    def get_mrc_configs(self):
        """Returns a list of the MRC configs in this setup."""
        return list(self._mrc_configs)

    def contains_mrc_config(self, mrc_config):
        return mrc_config in self.mrc_configs

    def get_filename(self):
        return self._filename

    def _on_child_modified(self, m):
        if m:
            self.modified = True

    def _set_modified(self, m):
        if not m:
            for cfg in self.mrc_configs:
                cfg.modified = False

            for cfg in self.device_configs:
                cfg.modified = False

    @modifies
    def set_filename(self, filename):
        self._filename = str(filename)
        self.filename_changed.emit(self.filename)

    mrc_configs     = pyqtProperty(list, get_mrc_configs)
    device_configs  = pyqtProperty(list, get_device_configs)
    filename        = pyqtProperty(str, get_filename, set_filename, notify=filename_changed)

class MRCConnectionConfig(ConfigObject):
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

    @modifies
    def reset_connection(self):
        self._mesycontrol_host = None
        self._mesycontrol_port = None
        self._serial_device = None
        self._serial_baud_rate = None
        self._tcp_host = None
        self._tcp_port = None

    @modifies
    def set_mesycontrol_host(self, host):
        if self.is_valid() and not self.is_mesycontrol_connection():
            raise ConfigError("Cannot set mesycontrol_host on non-mesycontrol connection.")
        self._mesycontrol_host = str(host)

    @modifies
    def set_mesycontrol_port(self, port):
        if self.is_valid() and not self.is_mesycontrol_connection():
            raise ConfigError("Cannot set mesycontrol_port on non-mesycontrol connection.")
        self._mesycontrol_port = int(port)

    @modifies
    def set_serial_device(self, device):
        if self.is_valid() and not self.is_serial_connection():
            raise ConfigError("Cannot set serial_device on non-serial connection.")
        self._serial_device = str(device)

    @modifies
    def set_serial_baud_rate(self, baud):
        if self.is_valid() and not self.is_serial_connection():
            raise ConfigError("Cannot set serial_baud_rate on non-serial connection.")
        self._serial_baud_rate = int(baud)

    @modifies
    def set_tcp_host(self, host):
        if self.is_valid() and not self.is_tcp_connection():
            raise ConfigError("Cannot set tcp_host on non-tcp connection.")
        self._tcp_host = str(host)

    @modifies
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

def make_device_config(device, fill_parameters):
    device_config         = DeviceConfig()
    device_config.idc     = device.idc
    device_config.bus     = device.bus
    device_config.address = device.address
    device_config.rc      = device.rc

    if fill_parameters:
        for profile in filter(lambda p: p.should_be_stored(), device.profile.parameters):
            address = profile.address
            value   = device.get_parameter(address)
            device_config.set_parameter_value(address, value)

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

class DeviceConfigBuilder(command.SequentialCommandGroup):
    def __init__(self, device, parent=None):
        super(DeviceConfigBuilder, self).__init__(parent)
        self.device = device

        for profile in filter(lambda p: p.should_be_stored(), device.profile.parameters):
            if not device.has_parameter(profile.address):
                self.add(mrc_command.ReadParameter(device, profile.address))

    def get_result(self):
        if self.has_failed():
            return super(DeviceConfigBuilder, self).get_result()

        return make_device_config(self.device, fill_parameters=True)

class DeviceConfigCompleter(command.SequentialCommandGroup):
    """Makes sure all parameters needed to complete this devices config are present.
    This command issues read requests for missing parameters. The device object
    will then automatically fill in missing config values.
    """
    def __init__(self, device, parent=None):
        super(DeviceConfigCompleter, self).__init__(parent)
        self.device = device
        self.log    = util.make_logging_source_adapter(__name__, self)

        param_filter = lambda pd: not pd.read_only and not pd.do_not_store
        required_parameters = filter(param_filter, device.profile.parameters)

        for param_descr in required_parameters:
            if device.config is None:
                self.log.warn("Device %s has no config object!")
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
        # Keep the original setup around to avoid any of the configs being
        # garbage collected.
        self._old_setup = registry.get('active_setup')
        registry.register('active_setup', self.setup)

        mrcs_to_remove = set(registry.get_mrcs())

        # Keep MRCs with a config in the new setup
        for mrc_config in self.setup.mrc_configs:
            mrc = registry.find_mrc_by_config(mrc_config)
            if mrc is not None:
                mrcs_to_remove.remove(mrc)

        # Remove MRCs without a config in the new setup
        for mrc in mrcs_to_remove:
            self.log.info("Removing MRC %s", mrc)
            mrc.disconnect()
            registry.unregister_mrc(mrc)

        for mrc_config in self.setup.mrc_configs:
            mrc = registry.find_mrc_by_config(mrc_config)

            if mrc is None:
                mrc = application_registry.instance.make_mrc_connection(
                        mrc_config=mrc_config, connect=True)
                self.log.info("Created MRC %s", mrc)
            else:
                self.log.info("Found MRC %s: applying config", mrc)
                mrc.config = mrc_config

            self._pending_mrcs.add(mrc)
            mrc.ready.connect(self._slt_on_mrc_ready)
            mrc.disconnected.connect(self._slt_on_mrc_disconnected)

            mrc.connect()
            if mrc.is_ready():
                self._on_mrc_ready(mrc)

        self._completion_check()

    def _slt_on_mrc_ready(self, is_ready):
        if not is_ready:
            return

        self._on_mrc_ready(self.sender())

    def _on_mrc_ready(self, mrc):
        self.log.info("MRC %s is ready. Loading configs", mrc)

        mrc.ready.disconnect(self._slt_on_mrc_ready)
        mrc.disconnected.disconnect(self._slt_on_mrc_disconnected)
        self._pending_mrcs.remove(mrc)

        for device_config in mrc.config.device_configs:
            device = mrc.get_device(device_config.bus, device_config.address)
            if not device.has_model():
                continue

            loader = config_loader.ConfigLoader(device, device_config)
            loader.stopped.connect(self._on_config_loader_stopped)
            self._pending_config_loaders.add(loader)
            loader.start()

        self._completion_check()

    def _slt_on_mrc_disconnected(self, info=None):
        self._on_mrc_disconnected(self.sender())

    def _on_mrc_disconnected(self, mrc):
        mrc.ready.disconnect(self._slt_on_mrc_ready)
        mrc.disconnected.disconnect(self._slt_on_mrc_disconnected)
        self._pending_mrcs.remove(mrc)
        self._failed = True
        self._completion_check()

    def _on_config_loader_stopped(self):
        config_loader = self.sender()
        config_loader.stopped.disconnect(self._on_config_loader_stopped)
        self._pending_config_loaders.remove(config_loader)
        self._failed = config_loader.has_failed()
        self._completion_check()

    def _completion_check(self):
        if len(self._pending_mrcs) == 0 and len(self._pending_config_loaders) == 0:
            self.setup.modified = False
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
