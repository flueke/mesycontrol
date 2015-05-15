#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtProperty
from qt import pyqtSignal
from qt import QtCore

import collections
import weakref

import future
import util

class MRCRegistry(QtCore.QObject):
    """Manages MRC instances"""

    mrc_added   = pyqtSignal(object)
    mrc_removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super(MRCRegistry, self).__init__(parent)
        self._mrcs = list()
        self.log   = util.make_logging_source_adapter(__name__, self)

    def add_mrc(self, mrc):
        if self.get_mrc(mrc.url) is not None:
            raise RuntimeError("MRC %s exists in MRCRegistry" % mrc.url)

        self.log.debug("add_mrc: %s %s", mrc, mrc.url)
        self._mrcs.append(mrc)
        self._mrcs.sort(key=lambda mrc: mrc.url)
        self.mrc_added.emit(mrc)

    def remove_mrc(self, mrc):
        try:
            self._mrcs.remove(mrc)
            self.mrc_removed.emit(mrc)
        except ValueError:
            raise ValueError("No such MRC %s" % mrc)

    def get_mrc(self, url):
        return next((mrc for mrc in self._mrcs if mrc.url == url), None)

    def get_mrcs(self):
        return list(self._mrcs)

    mrcs = pyqtProperty(list, get_mrcs)

class MRC(QtCore.QObject):
    device_added   = pyqtSignal(object)
    device_removed = pyqtSignal(object)

    def __init__(self, url, parent=None):
        super(MRC, self).__init__(parent)
        self._url       = str(url)
        self._devices   = list()

    def add_device(self, device):
        if self.get_device(device.bus, device.address) is not None:
            raise ValueError("Device at (%d, %d) exists", device.bus, device.address)

        self._devices.append(device)
        self._devices.sort(key=lambda device: (device.bus, device.address))
        device.mrc = self
        self.device_added.emit(device)

    def remove_device(self, device):
        try:
            self._devices.remove(device)
            device.mrc = None
            self.device_removed.emit(device)
        except ValueError:
            raise ValueError("No Device %s" % device)

    def get_url(self):
        return self._url

    def get_device(self, bus, address):
        compare = lambda d: (d.bus, d.address) == (bus, address)
        return next((dev for dev in self._devices if compare(dev)), None)
    
    def get_devices(self, bus=None):
        if bus is None:
            return list(self._devices)
        return [d for d in self._devices if d.bus == bus]

    #def __str__(self):
    #    return 'MRC(url="%s")' % self.url

    url = pyqtProperty(str, get_url)

class ReadResult(collections.namedtuple("ReadResult", "bus device address value")):
    def __int__(self):
        return self.value

class SetResult(collections.namedtuple("SetResult", ReadResult._fields + ('requested_value',))):
    def __int__(self):
        return self.value

class Device(QtCore.QObject):
    idc_changed     = pyqtSignal(int)
    mrc_changed     = pyqtSignal(object)
    parameter_changed = pyqtSignal(int, object)

    def __init__(self, bus, address, idc, parent=None):
        super(Device, self).__init__(parent)
        self._bus       = int(bus)
        self._address   = int(address)
        self._idc       = int(idc)
        self._mrc       = None
        self._memory    = dict()

    def get_bus(self):
        return self._bus

    def get_address(self):
        return self._address

    def get_idc(self):
        return self._idc

    def set_idc(self, idc):
        self._idc = int(idc)
        self.idc_changed.emit(self.idc)

    def get_mrc(self):
        return None if self._mrc is None else self._mrc()

    def set_mrc(self, mrc):
        self._mrc = None if mrc is None else weakref.ref(mrc)
        self.mrc_changed.emit(self.mrc)

    def get_parameter(self, address):
        """Get a parameter from the devices memory cache if available.
        Otherwise use Device.read_parameter() to read the parameter from the
        hardware.
        Returns a Future whose result is a ReadResult instance.
        """
        if self.has_cached_parameter(address):
            result = ReadResult(self.bus, self.address, address,
                    self.get_cached_parameter(address))
            return future.Future().set_result(result)

        return self.read_parameter(address)

    def read_parameter(self, address):
        """Read a parameter from the device. Subclass implementations must call
        Device.set_cached_parameter() on read success to update the local
        memory cache.
        This method is expected to return a Future whose result is a ReadResult
        instance.
        """
        raise NotImplementedError

    def set_parameter(self, address, value):
        raise NotImplementedError

    def get_cached_parameter(self, address):
        return self._memory.get(address, None)

    def set_cached_parameter(self, address, value):
        changed = self.get_cached_parameter(address) != value
        self._memory[address] = value
        if changed:
            self.parameter_changed.emit(address, value)

    def has_cached_parameter(self, address):
        return address in self._memory

    def get_cached_memory(self):
        return dict(self._memory)

    def __str__(self):
        return 'Device(bus=%d, address=%d, idc=%d, mrc=%s)' % (
                self.bus, self.address, self.idc, self.mrc)

    bus     = pyqtProperty(int, get_bus)
    address = pyqtProperty(int, get_address)
    idc     = pyqtProperty(int, get_idc, set_idc, notify=idc_changed)
    mrc     = pyqtProperty(object, get_mrc, set_mrc, notify=mrc_changed)
