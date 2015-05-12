#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtProperty
from qt import pyqtSignal

import basic_model as bm

class Setup(bm.MRCRegistry):
    modified_changed = pyqtSignal(bool)
    filename_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super(Setup, self).__init__(parent)
        self._modified = False
        self._filename = str()

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

    modified = pyqtProperty(bool, is_modified, set_modified, notify=modified_changed)
    filename = pyqtProperty(str, get_filename, set_filename, notify=filename_changed)

class MRC(bm.MRC):
    def __init__(self, url, parent=None):
        super(MRC, self).__init__(url, parent)

class Device(bm.Device):
    def __init__(self, bus, address, idc, parent=None):
        super(Device, self).__init__(bus, address, idc, parent)
