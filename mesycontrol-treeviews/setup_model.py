#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtProperty
from qt import pyqtSignal
from qt import QtCore

class Setup(QtCore.QObject):
    modified_changed = pyqtSignal(bool)
    filename_changed = pyqtSignal(str)
    mrc_added        = pyqtSignal(object)
    mrc_removed      = pyqtSignal(object)

    def __init__(self, parent=None):
        super(Setup, self).__init__(parent)
        self._modified = False
        self._filename = str()
        self._mrcs     = list()

    def set_modified(self, b):
        self._modified = bool(b)
        self.modified_changed.emit(self.modified)

    def is_modified(self):
        return self._modified

    def set_filename(self, filename):
        self._filename = str(filename)
        self.filename_changed.emit(self.filename)

    def get_filename(self):
        return self._filename

    def add_mrc(self, mrc):
        if self.get_mrc(mrc.url) is not None:
            raise RuntimeError("MRC %s exists in Setup" % mrc.url)

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

    modified = pyqtProperty(bool, is_modified, set_modified, notify=modified_changed)
    filename = pyqtProperty(str, get_filename, set_filename, notify=filename_changed)
    mrcs     = pyqtProperty(list, get_mrcs)

class MRC(QtCore.QObject):
    url_changed    = pyqtSignal(str)
    device_added   = pyqtSignal(object)
    device_removed = pyqtSignal(object)

    def __init__(self, parent=None):
        self._devices = list()

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

    def get_device(self, bus, address):
        compare = lambda d: (d.bus, d.address) == (bus, address)
        return next((dev for dev in self._devices if compare(dev)), None)

    def get_url(self):
        return self._url

    def set_url(self, url):
        self._url = str(url)
        self.url_changed.emit(self.url)

    url = pyqtProperty(str, get_url, set_url, notify=url_changed)
