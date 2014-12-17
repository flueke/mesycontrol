#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from command import Callable
from command import CommandException
from command import SequentialCommandGroup
from mrc_command import ReadParameter
from mrc_command import SetParameter
import util

class ConfigLoader(SequentialCommandGroup):
    def __init__(self, device, device_config, parent=None):
        super(ConfigLoader, self).__init__(parent)
        self.log         = util.make_logging_source_adapter(__name__, self)
        self.device      = device
        self.config      = device_config
        self._prepare()

    def _prepare(self):
        self.clear()

        def assign_config():
            if self.device.config is not self.config:
                self.config.bus     = self.device.bus
                self.config.address = self.device.address
                self.device.assign_config(self.config)

        self.add(Callable(assign_config))

        old_polling_state = self.device.mrc.polling

        def disable_polling():
            self.device.mrc.polling = False

        self.add(Callable(disable_polling))

        dev_profile = self.device.profile

        # Set critical params to safe values first
        for param_profile in dev_profile.get_critical_parameters():
            self.add(SetParameter(self.device, param_profile.address, param_profile.safe_value))

        # Set non-critical config values in device profile order
        for param_profile in dev_profile.get_non_critical_parameters():
            if not param_profile.read_only and self.config.contains_parameter(param_profile.address):
                self.add(SetParameter(self.device, param_profile.address,
                    self.config.get_parameter_value(param_profile.address)))

        # Set critical param config values
        for param_profile in dev_profile.get_critical_parameters():
            if self.config.contains_parameter(param_profile.address):
                self.add(SetParameter(self.device, param_profile.address,
                    self.config.get_parameter_value(param_profile.address)))

        def load_extensions():
            for name, value in self.config.get_extensions().iteritems():
                self.log.debug("Loading device extension '%s'->'%s'", name, value)
                setattr(self.device, name, value)

        def set_rc():
            if self.config.rc is not None:
                self.device.rc = self.config.rc

        def enable_polling():
            self.device.mrc.polling = old_polling_state

        self.add(Callable(load_extensions))
        self.add(Callable(set_rc))
        self.add(Callable(enable_polling))

class ConfigVerifier(SequentialCommandGroup):
    def __init__(self, device_model, device_config, parent=None):
        super(ConfigVerifier, self).__init__(parent)
        self.device      = device_model
        self.config      = device_config

        if None not in (self.device, self.config):
            self._prepare()

    def _prepare(self):
        self.clear()

        for param in filter(lambda p: p.value is not None, self.config.get_parameters()):
            self.add(ReadParameter(self.device, param.address))

    def _start(self):
        if None in (self.device, self.config):
            raise CommandException("device and config needed")

        self._prepare()
        super(ConfigVerifier, self)._start()

    def get_result(self):
        for cmd in self._commands:
            if cmd.has_failed() or cmd.get_result() is None:
                return False

            device_value = cmd.get_result()
            config_value = self.config.get_parameter(cmd.address).value

            if device_value != config_value:
                return False

        return True
