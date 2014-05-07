#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal
import logging

def load_values(mrc_model, values):
    for bus, dev, par, value in values:
        mrc_model.setParameter(bus, dev, par, value)

def verify_values(mrc_model, values):
    for bus, dev, par, value in values:
        actual_value = mrc_model.readParameter(bus, dev, par)
        if value != actual_value:
            raise Exception("verification failed!")

# TODO: suspend polling during config loading (preferably for the complete MRC)
# TODO: detect and handle error messages from the server
class ConfigLoader(QtCore.QObject):
    sig_complete = pyqtSignal(bool)

    def __init__(self, device_model=None, device_config=None, device_description=None, parent=None):
        super(ConfigLoader, self).__init__(parent)
        self.device_model       = device_model
        self.device_config      = device_config
        self.device_description = device_description
        self.log                = logging.getLogger("ConfigLoader")
        self.result             = False

    def start(self):
        assert self.device_model is not None \
                and self.device_config is not None \
                and self.device_description is not None

        self._to_set = [(p.address, p.safe_value) for p in self.device_description.get_critical_parameters()]

        for param_cfg in self.device_config.get_parameters():
            param_descr = self.device_description.get_parameter_by_address(param_cfg.address)
            if param_descr is None or (not param_descr.critical and not param_descr.read_only):
                self._to_set.append((param_cfg.address, param_cfg.value))

        for param_cfg in self.device_config.get_parameters():
            param_descr = self.device_description.get_parameter_by_address(param_cfg.address)
            if param_descr is not None and param_descr.critical and not param_descr.read_only:
                self._to_set.append((param_cfg.address, param_cfg.value))

        self.log.info("Loading %d values", len(self._to_set))
        self.device_model.sig_parameterSet.connect(self._slt_parameterSet)
        self._set_next_param()

    def _set_next_param(self):
        if len(self._to_set):
            addr, value = self._to_set[0]
            self.device_model.setParameter(addr, value)
        else:
            self.device_model.sig_parameterSet.disconnect(self._slt_parameterSet)
            self.result = True
            self.sig_complete.emit(True)

    def _slt_parameterSet(self, addr, value):
        if (addr, value) == self._to_set[0]:
            self._to_set.pop(0)
            self._set_next_param()

class ConfigVerifier(QtCore.QObject):
    sig_complete = pyqtSignal(bool)

    def __init__(self, device_model=None, device_config=None, device_description=None, parent=None):
        super(ConfigVerifier, self).__init__(parent)
        self.device_model       = device_model
        self.device_config      = device_config
        self.device_description = device_description
        self.log                = logging.getLogger("ConfigVerifier")
        self.result             = False

    def start(self):
        assert self.device_model is not None \
                and self.device_config is not None \
                and self.device_description is not None

        self._to_verify = [(p.address, p.value) for p in self.device_config.get_parameters() if p.value is not None]
        self.log.info("Verifying %d values", len(self._to_verify))
        self.device_model.sig_parameterRead.connect(self._slt_parameterRead)
        self._read_next_param()

    def _read_next_param(self):
        if len(self._to_verify):
            addr, value = self._to_verify[0]
            self.device_model.readParameter(addr, True)
        else:
            self.device_model.sig_parameterRead.disconnect(self._slt_parameterRead)
            self.result = True
            self.sig_complete.emit(True)

    def _slt_parameterRead(self, addr, value):
        v_addr, v_value = self._to_verify[0]
        if addr == v_addr:
            if v_value == value:
                self._to_verify.pop(0)
                self._read_next_param()
            else:
                self.device_model.sig_parameterRead.disconnect(self._slt_parameterRead)
                self.result = False
                self.failed_param = (addr, value, v_value)
                self.sig_complete.emit(False)
