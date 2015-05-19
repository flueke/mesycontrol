#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import wraps
from qt import pyqtProperty
from qt import pyqtSignal

import basic_model as bm
import future

def modifies(f):
    """Method decorator which executes `wrapped_object.set_modified(True)'
    after successful method invokation."""
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        ret = f(self, *args, **kwargs)
        self.set_modified(True)
        return ret
    return wrapper

# I would've liked to use a ModifiedMixin here but PyQt4 does not seem to
# support it at all. Example:
# class ModifiedMixin(object):
#       modified_changed = pyqtSignal(bool)
#       def set_modified(self, m):
#           self._modified = m
#           self.modified_changed.emit(m)
#
# Instantiation is ok but trying to connect the modified_changed signal yields
# an error.

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

    @modifies
    def set_filename(self, filename):
        self._filename = str(filename)
        self.filename_changed.emit(self.filename)

    def get_filename(self):
        return self._filename

    add_mrc     = modifies(bm.MRCRegistry.add_mrc)
    remove_mrc  = modifies(bm.MRCRegistry.remove_mrc)

    modified = pyqtProperty(bool, is_modified, set_modified, notify=modified_changed)
    filename = pyqtProperty(str, get_filename, set_filename, notify=filename_changed)

class MRC(bm.MRC):
    modified_changed    = pyqtSignal(bool)
    name_changed        = pyqtSignal(str)

    def __init__(self, url, parent=None):
        super(MRC, self).__init__(url, parent)
        self._name = str()

    def set_modified(self, b):
        self._modified = bool(b)
        self.modified_changed.emit(self.modified)

    def is_modified(self):
        return self._modified

    def get_name(self):
        return self._name

    @modifies
    def set_name(self, name):
        self._name = str(name)
        self.name_changed.emit(self.name)

    set_url         = modifies(bm.MRC.set_url)
    add_device      = modifies(bm.MRC.add_device)
    remove_device   = modifies(bm.MRC.remove_device)

    modified    = pyqtProperty(bool, is_modified, set_modified, notify=modified_changed)
    name        = pyqtProperty(str, get_name, set_name, notify=name_changed)

class Device(bm.Device):
    modified_changed    = pyqtSignal(bool)
    name_changed        = pyqtSignal(str)

    def __init__(self, bus, address, idc, parent=None):
        super(Device, self).__init__(bus, address, idc, parent)

    def set_modified(self, b):
        self._modified = bool(b)
        self.modified_changed.emit(self.modified)

    def is_modified(self):
        return self._modified

    def get_name(self):
        return self._name

    @modifies
    def set_name(self, name):
        self._name = str(name)
        self.name_changed.emit(self.name)

    set_bus     = modifies(bm.Device.set_bus)
    set_address = modifies(bm.Device.set_address)
    set_idc     = modifies(bm.Device.set_idc)
    set_mrc     = modifies(bm.Device.set_mrc)

    def read_parameter(self, address):
        # This is either called directly or by bm.Device.get_parameter in case
        # the parameter is not cached. Let's re-check the cache here to make
        # the first case succeed and not force the user to use get_parameter
        # for device config objects.
        if self.has_cached_parameter(address):
            result = bm.ReadResult(self.bus, self.address, address,
                    self.get_cached_parameter(address))
            return bm.ResultFuture().set_result(result)
        return future.Future().set_exception(ValueError("Parameter %d not in Device config" % address))

    @modifies
    def set_parameter(self, address, value):
        self.set_cached_parameter(address, value)
        result = bm.SetResult(self.bus, self.address, address,
                self.get_cached_parameter(address), value)
        return bm.ResultFuture().set_result(result)

    modified    = pyqtProperty(bool, is_modified, set_modified, notify=modified_changed)
    name        = pyqtProperty(str, get_name, set_name, notify=name_changed)

s = Setup()
print s.modified
mrc = MRC("foobar")
def on_mrc_added(mrc):
    print s.modified, mrc
s.mrc_added.connect(on_mrc_added)
s.add_mrc(mrc)
print s.modified
print s.add_mrc
print s.add_mrc.__doc__
