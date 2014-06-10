#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import application_model
import config
from config import make_connection_config
import mrc_connection
from config_loader import ConfigLoader, ConfigVerifier
from command import ParallelCommandGroup, SequentialCommandGroup
from mrc_command import ReadParameter, Scanbus
from device_description import DeviceDescription

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
        # FIXME: Groups and names connection configs by info string for now
        connection_config = make_connection_config(device.mrc_model.connection)
        connection_config.name = connection_config.get_connection_info()
        self._connection_configs[connection_config.name] = connection_config

        device_descr = self.app_model.get_device_description_by_idc(device.idc)

        if device_descr is None:
            device_descr = DeviceDescription.makeGenericDescription(device.idc)

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
            return None

        # All child commands completed without error. This means the device
        # models memory has been read and it's thus ok to call
        # make_device_config().

        ret = config.Config()
        ret.mrc_connections.extend(self._connection_configs.itervalues())

        for device in self._devices:
            device_config = config.make_device_config(device)
            # FIXME: name as above
            connection_config = make_connection_config(device.mrc_model.connection)
            device_config.connection_name = connection_config.get_connection_info()
            ret.device_configs.append(device_config)

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
            raise RuntimeError("Device IDC mismatch (bus=%d, dev=%id, idc=%d, expected idc=%d" %
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
                # Try to find an existing connection
                f = lambda conn: make_connection_config(conn).get_connection_info() == connection_name
                connection = filter(f, self.app_model.mrc_connections)[0]
            except IndexError:
                try:
                    # Find the connection config referenced by the device
                    # config and use it to create a new connection.
                    connection_config = filter(lambda cfg: cfg.name == connection_name, config.mrc_connections)[0]
                    connection = mrc_connection.factory(config=connection_config)
                    self.app_model.registerConnection(connection)
                except IndexError:
                    raise RuntimeError("Connection not found: %s" % connection_name)

            if not connection.is_connected():
                connection.connect()

            mrc = connection.mrc_model

            if mrc not in self._mrc_to_device_configs:
                self._mrc_to_device_configs[mrc] = list()
            self._mrc_to_device_configs[mrc].append(device_config)


        #scanbus_parallel = ParallelCommandGroup()
        #for mrc in self._mrc_to_device_configs.keys():
        #    scanbus_commands = SequentialCommandGroup()
        #    for bus in range(2):
        #        scanbus_commands.add(ScanbusCommand(mrc, bus))
        #    scanbus_parallel.add(scanbus_commands)

        #self.add(scanbus_parallel)

        ## Commands grouped by MRC
        #load_setup_parallel = ParallelCommandGroup()

        #for mrc, cfgs in self._mrc_to_device_configs.iteritems():
        #    # One sequential command per mrc loading the device configs
        #    load_configs_sequential = SequentialCommandGroup()
        #    for cfg in cfgs:
        #        descr = self.app_model.get_device_description_by_idc(cfg.device_idc)
        #        if descr is None:
        #            descr = DeviceDescription.makeGenericDescription(cfg.device_idc)
        #        load_configs_sequential.add(DelayedConfigLoader(mrc, cfg, descr))

        #    load_setup_parallel.add(load_configs_sequential)

        #self.add(load_setup_parallel)

        for mrc in self._mrc_to_device_configs.keys():
            for bus in range(2):
                self.add(Scanbus(mrc, bus))

        for mrc, cfgs in self._mrc_to_device_configs.iteritems():
            for cfg in cfgs:
                descr = self.app_model.get_device_description_by_idc(cfg.device_idc)
                if descr is None:
                    descr = DeviceDescription.makeGenericDescription(cfg.device_idc)
                self.add(DelayedConfigLoader(mrc, cfg, descr))
