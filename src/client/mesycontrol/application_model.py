#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import pyqtProperty
from mesycontrol.protocol import Message
import logging
import weakref

class ApplicationModel(QtCore.QObject):
    sig_connection_added = pyqtSignal(object)

    def __init__(self, parent = None):
        super(ApplicationModel, self).__init__(parent)
        self.device_descriptions = set()
        self.mrc_connections = list()

    def registerConnection(self, conn):
        conn.setParent(self)
        self.mrc_connections.append(conn)
        self.sig_connection_added.emit(conn)

    def shutdown(self):
        while len(self.mrc_connections):
            conn = self.mrc_connections.pop()
            conn.stop()
            del conn

    def load_system_descriptions(self):
        import importlib
        for mod_name in ('device_description_mhv4', 'device_description_mhv4_800v', 'device_description_mscf16'):
            mod = importlib.import_module('mesycontrol.' + mod_name)
            self.device_descriptions.add(mod.get_device_description())

    def get_device_description_by_idc(self, idc):
        try:
            return filter(lambda d: d.idc == idc, self.device_descriptions)[0]
        except IndexError:
            return None

    def get_device_description_by_name(self, name):
        try:
            return filter(lambda d: d.name == name, self.device_descriptions)[0]
        except IndexError:
            return None

instance = ApplicationModel()

class MRCModel(QtCore.QObject):
    #: Emitted after both mrc busses have been scanned. The argument is the
    #: complete bus data dictionary.
    sig_bus_data_complete   = pyqtSignal(dict)
    #: Args: bus, dev, par, val
    sig_parameterRead       = pyqtSignal(int, int, int, int)
    #: Args: bus, dev, par, val
    sig_parameterSet        = pyqtSignal(int, int, int, int)
    #: Args: bus, dev, rc_status
    sig_rcSet               = pyqtSignal(int, int, bool)

    sig_connected           = pyqtSignal()
    sig_disconnected        = pyqtSignal()

    def __init__(self, connection, parent=None):
        super(MRCModel, self).__init__(parent)
        self.bus_data = {}
        self.device_models = {}
        self.connection = weakref.ref(connection)
        self.client     = weakref.ref(connection.tcp_client)
        self.client().sig_connected.connect(self._slt_client_connected)
        self.client().sig_disconnected.connect(self._slt_client_disconnected)
        self.client().sig_message_received.connect(self._slt_message_received)
        self.client().sig_queue_empty.connect(self._slt_client_queue_empty)
        self.poll_set = set()
        self.log = logging.getLogger("MRCModel")

    def get_mrc_address_string(self):
        return self.connection().get_mrc_address_string()

    def scanbus(self, bus):
      self.client().queue_request(Message('request_scanbus', bus=bus))

    def readParameter(self, bus, dev, par):
      self.client().queue_request(Message('request_read', bus=bus, dev=dev, par=par))

    def setParameter(self, bus, dev, par, value):
      self.client().queue_request(Message('request_set', bus=bus, dev=dev, par=par, val=value))

    def setRc(self, bus, dev, rc):
      self.client().queue_request(Message('request_rc_on' if rc else 'request_rc_off', bus=bus, dev=dev))

    def addPollParameter(self, bus, dev, par):
        try:
            par = int(par)
        except TypeError:
            par = par.address

        self.poll_set.add((bus, dev, par))
        if self.client().get_request_queue_size() == 0:
            self._slt_client_queue_empty() # Init polling

    def addPollParameters(self, bus, dev, pars):
        for par in pars:
            self.addPollParameter(bus, dev, par)

    def removePollParameter(self, bus, dev, par):
        self.poll_set.discard((bus, dev, par))

    def removePollParameters(self, bus, dev):
        remove_set = set(filter(lambda t: bus == t[0] and dev == t[1], self.poll_set))
        self.poll_set.difference_update(remove_set)

    def _slt_client_connected(self, host, port):
        self.log.info("Connected to %s:%d", host, port)
        self.scanbus(0)
        self.scanbus(1)
        self.sig_connected.emit()

    def _slt_client_disconnected(self):
        self.sig_disconnected.emit()

    def _slt_message_received(self, msg):
        self.log.debug("Received message=%s", msg)

        if msg.get_type_name() == 'response_scanbus':
            # TODO: handle changes to the scanbus data:
            # device added/removed, address conflict appeared/disappeared, device idc changed
            if msg.bus not in self.bus_data:
                self.bus_data[msg.bus] = {}

            if msg.bus not in self.device_models:
                self.device_models[msg.bus] = {}

            self.bus_data[msg.bus] = msg.bus_data

            for dev in range(16):
                idc, rc = msg.bus_data[dev]

                if rc in (0, 1):
                    if idc > 0 and dev not in self.bus_data[msg.bus]:
                        self.device_models[msg.bus][dev] = DeviceModel(msg.bus, dev, idc, rc, mrc_model=self, parent=self)
                    elif idc > 0:
                        self.device_models[msg.bus][dev].rc = rc

            if len(self.bus_data) == 2:
                self.sig_bus_data_complete.emit(self.bus_data)

        elif msg.get_type_name() == 'response_read':
            self.sig_parameterRead.emit(msg.bus, msg.dev, msg.par, msg.val)
        elif msg.get_type_name() in ('response_set', 'notify_set'):
            self.sig_parameterSet.emit(msg.bus, msg.dev, msg.par, msg.val)
        else:
            self.log.warning("Unhandled message %s", msg)

    def _slt_client_queue_empty(self):
        if len(self.poll_set) == 0:
            return
        #self.log.debug("Polling %d parameters", len(self.poll_set))
        for bus, dev, par in self.poll_set:
            self.readParameter(bus, dev, par)

class DeviceModel(QtCore.QObject):
    #: Args: par, val
    sig_parameterRead       = pyqtSignal(int, int)
    #: Args: par, val
    sig_parameterSet        = pyqtSignal(int, int)
    #: Args: par, old_val, new_val. Only emitted if the value actually differs
    #: from the previously known value.
    sig_parameterChanged    = pyqtSignal(int, int, int)
    #: Arg: rc_status
    sig_rcSet               = pyqtSignal(bool)

    def __init__(self, bus, dev, idc, rc, mrc_model, parent=None):
        super(DeviceModel, self).__init__(parent)
        self._mrc_model = weakref.ref(mrc_model)
        self.bus       = bus
        self.dev       = dev
        self.idc       = idc
        self.rc        = rc
        self.memory   = {}
        
        self.mrc_model.sig_parameterRead.connect(self._slt_parameterRead)
        self.mrc_model.sig_parameterSet.connect(self._slt_parameterSet)
        self.mrc_model.sig_rcSet.connect(self._slt_rcSet)

    def readParameter(self, address, reread = False):
        if not reread and address in self.memory:
            self.sig_parameterRead.emit(address, self.memory[address])
        else:
            self.mrc_model.readParameter(self.bus, self.dev, address)

    def setParameter(self, address, value):
        self.mrc_model.setParameter(self.bus, self.dev, address, value)

    def addPollParameter(self, address):
        self.mrc_model.addPollParameter(self.bus, self.dev, address)

    def addPollParameters(self, params):
        self.mrc_model.addPollParameters(self.bus, self.dev, params)

    def removePollParameter(self, address):
        self.mrc_model.removePollParameter(self.bus, self.dev, address)

    def clearPollParameters(self):
        self.mrc_model.removePollParameters(self.bus, self.dev)

    def setRc(self, on_off):
        if on_off != self.rc:
            self.mrc_model.setRc(self.bus, self.dev, on_off)

    def getMRCModel(self):
        return self._mrc_model() if self._mrc_model is not None else None

    def _slt_parameterRead(self, bus, dev, address, value):
        if bus == self.bus and dev == self.dev:
            old_value = self.memory.get(address, None)
            self.memory[address] = value
            self.sig_parameterRead.emit(address, value)
            if old_value != value:
                self.sig_parameterChanged.emit(address, old_value, value)

    def _slt_parameterSet(self, bus, dev, address, value):
        if bus == self.bus and dev == self.dev:
            old_value = self.memory.get(address, None)
            self.memory[address] = value
            self.sig_parameterSet.emit(address, value)
            if old_value != value:
                self.sig_parameterChanged.emit(address, old_value, value)

    def _slt_rcSet(self, bus, dev, on_off):
        if bus == self.bus and dev == self.dev:
            self.rc = on_off
            self.sig_rcSet.emit(on_off)

    mrc_model = pyqtProperty(object, getMRCModel)


class DeviceViewModel(QtCore.QObject):
    sig_parameterRead    = pyqtSignal([str, int], [int, int])
    sig_parameterSet     = pyqtSignal([str, int], [int, int])
    sig_rcSet            = pyqtSignal(bool)

    def __init__(self, device_model, device_description, device_config=None, parent=None):
        super(DeviceViewModel, self).__init__(parent)

        self._device_model      = weakref.ref(device_model)
        self.device_description = device_description
        self.device_config      = device_config

        device_model.sig_parameterRead.connect(self._slt_parameterRead)
        device_model.sig_parameterSet.connect(self._slt_parameterSet)
        device_model.sig_rcSet.connect(self.sig_rcSet)

    def readParameter(self, name_or_address, reread = False):
        self.device_model.readParameter(self._name2address(name_or_address), reread)

    def setParameter(self, name_or_address, value):
        self.device_model.setParameter(self._name2address(name_or_address), value)

    def setRc(self, on_off):
        self.device_model.setRc(on_off)

    def getDeviceModel(self):
        return self._device_model()

    def setDeviceDescription(self, descr):
        self._device_description = descr
        self.device_model.clearPollParameters()
        poll_params = filter(lambda p: p.poll, descr.parameters.values())
        self.device_model.addPollParameters(poll_params)

    def getDeviceDescription(self):
        return self._device_description

    def setDeviceConfig(self, config):
        self._device_config = weakref.ref(config) if config is not None else None

    def getDeviceConfig(self):
        return self._device_config() if self._device_config is not None else None

    def _name2address(self, name):
        address = self.device_description.get_parameter_by_name(name)
        if address is not None:
            return address
        return name

    def _slt_parameterRead(self, address, value):
        self.sig_parameterRead[int, int].emit(address, value)
        param_desc = self.device_description.get_parameter_by_address(address)
        if param_desc is not None and param_desc.name is not None:
           self.sig_parameterRead[str, int].emit(param_desc.name, value)

    def _slt_parameterSet(self, address, value):
        self.sig_parameterSet[int, int].emit(address, value)
        param_desc = self.device_description.get_parameter_by_address(address)
        if param_desc is not None and param_desc.name is not None:
           self.sig_parameterSet[str, int].emit(param_desc.name, value)

    device_model       = pyqtProperty(object, getDeviceModel)
    device_description = pyqtProperty(object, getDeviceDescription, setDeviceDescription)
    device_config      = pyqtProperty(object, getDeviceConfig, setDeviceConfig)

class MHV4ViewModel(DeviceViewModel):
    def __init__(self, device_model, device_description, device_config=None):
        super(MHV4ViewModel, self).__init__(device_model, device_description, device_config)

    def setChannelsEnabled(self, enabled):
        for i in range(4):
            self.setParameter("channel%d_enable_write" % i, 1 if enabled else 0)

    def enableAllChannels(self):
        self.setChannelsEnabled(True)

    def disableAllChannels(self):
        self.setChannelsEnabled(False)
