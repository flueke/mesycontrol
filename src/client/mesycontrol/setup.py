#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import application_model
import config
from config import make_connection_config
import mrc_connection
from config_loader import ConfigLoader, ConfigVerifier
from command import SequentialCommandGroup
from mrc_command import ReadParameter, Scanbus
from device_description import DeviceDescription
import util

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

class SetupBuilder(SequentialCommandGroup):
    def __init__(self, parent=None):
        super(SetupBuilder, self).__init__(parent)
        self._devices = set()
        self._connection_configs = dict()
        self.app_model = application_model.instance

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

        ret = config.Config()
        ret.connection_configs.extend(self._connection_configs.itervalues())
        ret.device_configs.extend(
                (config.make_device_config(device) for device in self._devices))

        return ret

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
        self.app_model = application_model.instance

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
                    descr = DeviceDescription.makeGenericDescription(cfg.device_idc)
                self.add(DelayedConfigLoader(mrc, cfg, descr))

    def _slt_connection_error(self, error_object):
        self._exception = error_object
        self._stopped(False)

