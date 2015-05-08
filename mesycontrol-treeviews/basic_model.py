#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtProperty
from qt import pyqtSignal
from qt import QtCore

class MRCRegistry(QtCore.QObject):
    """Manages MRC instances"""

    mrc_added   = pyqtSignal(object)
    mrc_removed = pyqtSignal(object)

    def __init__(self, parent=None):
        super(MRCRegistry, self).__init__(parent)
        self._mrcs = list()

    def add_mrc(self, mrc):
        if self.get_mrc(mrc.url) is not None:
            raise RuntimeError("MRC %s exists in MRCRegistry" % mrc.url)

        self._mrcs.append(mrc)
        self._mrcs.sort(key=lambda mrc: mrc.url)
        self.mrc_added.emit(mrc)

    def remove_mrc(self, mrc):
        try:
            self._mrcs.remove(mrc)
            self.mrc_removed.emit(mrc)
        except ValueError:
            raise ValueError("No such MRC %s" % mrc.url)

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
        self._url       = url
        self._devices   = list()

    def add_device(self, device):
        if self.get_device(device.bus, device.address) is not None:
            raise RuntimeError("Device at (%d, %d) exists", device.bus, device.address)

        self._devices.append(device)
        self._devices.sort(key=lambda device: (device.bus, device.address))
        self.device_added.emit(device)

    def remove_device(self, device):
        try:
            self._devices.remove(device)
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

class Device(QtCore.QObject):
    idc_changed     = pyqtSignal(int)

    def __init__(self, bus, address, idc, parent=None):
        super(Device, self).__init__(parent)
        self._bus       = int(bus)
        self._address   = int(address)
        self._idc       = int(idc)

    def get_bus(self):
        return self._bus

    def get_address(self):
        return self._address

    def get_idc(self):
        return self._idc

    def set_idc(self, idc):
        self._idc = int(idc)
        self.idc_changed.emit(self.idc)

    def __str__(self):
        return 'Device(bus=%d, address=%d, idc=%d)' % (
                self.bus, self.address, self.idc)

    bus     = pyqtProperty(int, get_bus)
    address = pyqtProperty(int, get_address)
    idc     = pyqtProperty(int, get_idc, set_idc, notify=idc_changed)
