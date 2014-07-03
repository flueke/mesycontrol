#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from command import Callable
from command import CommandException
from command import SequentialCommandGroup
from mrc_command import ReadParameter, SetParameter

class ConfigLoader(SequentialCommandGroup):
    def __init__(self, device_model, device_config, device_description, parent=None):
        super(ConfigLoader, self).__init__(parent)
        self.device      = device_model
        self.config      = device_config
        self.description = device_description

        if None not in (self.device, self.config, self.description):
            self._prepare()

    def _prepare(self):
        self.clear()

        # Set critical params to safe values first
        for param_descr in self.description.get_critical_parameters():
            self.add(SetParameter(self.device, param_descr.address, param_descr.safe_value))

        # Set values from config
        for param_cfg in self.config.get_parameters():
            param_descr = self.description.get_parameter_by_address(param_cfg.address)

            if (param_descr is None
                    or (not param_descr.critical
                        and not param_descr.read_only
                        and not param_descr.do_not_store)):
                self.add(SetParameter(self.device, param_cfg.address, param_cfg.value))

        # Set critical param config values
        for param_cfg in self.config.get_parameters():
            param_descr = self.description.get_parameter_by_address(param_cfg.address)
            if param_descr is not None and param_descr.critical:
                self.add(SetParameter(self.device, param_cfg.address, param_cfg.value))

        def set_name():
            self.device.name = self.config.name

        self.add(Callable(set_name))

    def _start(self):
        if None in (self.device, self.config, self.description):
            raise CommandException("device, config and description needed")

        self._prepare()
        super(ConfigLoader, self)._start()

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
