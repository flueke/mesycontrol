#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import wraps
from qt import pyqtProperty
from qt import pyqtSignal

import basic_model as bm

def modifies(f):
    """Method decorator which executes `wrapped_object.set_modified(True)'
    if the wrapped method returns a non-false value."""
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        ret = f(self, *args, **kwargs)
        if ret:
            self.set_modified(True)
        return ret
    return wrapper

def _set_modified(self, b):
    b = bool(b)
    self._set_modified_hook(b)
    if self.modified != b:
        self._modified = b
        self.modified_changed.emit(self.modified)

class Setup(bm.MRCRegistry):
    modified_changed = pyqtSignal(bool)
    filename_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super(Setup, self).__init__(parent)
        self._modified = False
        self._filename = str()

    set_modified = _set_modified

    def _set_modified_hook(self, b):
        if not b:
            for mrc in self.mrcs:
                mrc.modified = False

    def is_modified(self):
        return self._modified

    @modifies
    def set_filename(self, filename):
        filename = str(filename)
        if self.filename != filename:
            self._filename = filename
            self.filename_changed.emit(self.filename)
            return True

    def get_filename(self):
        return self._filename

    @modifies
    def add_mrc(self, mrc):
        super(Setup, self).add_mrc(mrc)
        mrc.modified_changed.connect(self._on_mrc_modified_changed)
        return True

    @modifies
    def remove_mrc(self, mrc):
        super(Setup, self).remove_mrc(mrc)
        mrc.modified_changed.disconnect(self._on_mrc_modified_changed)
        return True

    def _on_mrc_modified_changed(self, is_modified):
        if is_modified:
            self.modified = True

    modified = pyqtProperty(bool, is_modified, set_modified, notify=modified_changed)
    filename = pyqtProperty(str, get_filename, set_filename, notify=filename_changed)

class MRC(bm.MRC):
    modified_changed    = pyqtSignal(bool)
    name_changed        = pyqtSignal(str)

    def __init__(self, url=None, parent=None):
        super(MRC, self).__init__(url, parent)
        self._modified = False
        self._name = str()

    set_modified = _set_modified

    def _set_modified_hook(self, b):
        if not b:
            for device in self.get_devices():
                device.modified = False

    def is_modified(self):
        return self._modified

    def get_name(self):
        return self._name

    @modifies
    def set_name(self, name):
        name = str(name)
        if self.name != name:
            self._name = name
            self.name_changed.emit(self.name)
            return True

    @modifies
    def add_device(self, device):
        super(MRC, self).add_device(device)
        device.modified_changed.connect(self._on_device_modified_changed)
        return True

    @modifies
    def remove_device(self, device):
        super(MRC, self).remove_device(device)
        device.modified_changed.disconnect(self._on_device_modified_changed)
        return True

    def _on_device_modified_changed(self, is_modified):
        if is_modified:
            self.modified = True

    set_url     = modifies(bm.MRC.set_url)

    modified    = pyqtProperty(bool, is_modified, set_modified, notify=modified_changed)
    name        = pyqtProperty(str, get_name, set_name, notify=name_changed)

class Device(bm.Device):
    modified_changed    = pyqtSignal(bool)
    name_changed        = pyqtSignal(str)
    extension_added     = pyqtSignal(str, object)
    extension_changed   = pyqtSignal(str, object)
    extension_removed   = pyqtSignal(str, object)

    def __init__(self, bus=None, address=None, idc=None, parent=None):
        super(Device, self).__init__(bus, address, idc, parent)
        self._modified = False
        self._name = str()
        self._extensions = dict()

    set_modified = _set_modified

    def _set_modified_hook(self, b):
        pass

    def is_modified(self):
        return self._modified

    def get_name(self):
        return self._name

    @modifies
    def set_name(self, name):
        name = str(name) if name is not None else str()
        if self.name != name:
            self._name = name
            self.name_changed.emit(self.name)
            return True

    set_bus     = modifies(bm.Device.set_bus)
    set_address = modifies(bm.Device.set_address)
    set_idc     = modifies(bm.Device.set_idc)
    set_cached_parameter = modifies(bm.Device.set_cached_parameter)
    clear_cached_parameter = modifies(bm.Device.clear_cached_parameter)
    clear_cached_memory = modifies(bm.Device.clear_cached_memory)

    def _read_parameter(self, address):
        # This is either called by bm.Device.read_parameter() or by
        # bm.Device.get_parameter() in case the parameter is not cached. Let's
        # re-check the cache here to make the first case succeed and not force
        # the user to use get_parameter for device config objects.
        if self.has_cached_parameter(address):
            result = bm.ReadResult(self.bus, self.address, address,
                    self.get_cached_parameter(address))
            return bm.ResultFuture().set_result(result)
        return bm.ResultFuture().set_exception(
                KeyError("Parameter %d not in Device config" % address))

    def _set_parameter(self, address, value):
        self.set_cached_parameter(address, value)

        result = bm.SetResult(self.bus, self.address, address,
                self.get_cached_parameter(address), value)

        return bm.ResultFuture().set_result(result)

    @modifies
    def set_extension(self, name, value):
        is_new = name not in self._extensions

        if self._extensions.get(name, None) != value:
            self._extensions[name] = value
            if is_new:
                self.extension_added.emit(name, value)
            else:
                self.extension_changed.emit(name, value)

            return True

    def get_extension(self, name):
        return self._extensions[name]

    def get_extensions(self):
        return dict(self._extensions)

    @modifies
    def remove_extension(self, name):
        value = self.get_extension(name)
        del self._extensions[name]
        self.extension_removed.emit(name, value)
        return True

    def __str__(self):
        return "%s.Device(id=%s, b=%d, a=%d, idc=%d, mrc=%s)" % (
                __name__, hex(id(self)), self.bus, self.address, self.idc, self.mrc)

    modified    = pyqtProperty(bool, is_modified, set_modified, notify=modified_changed)
    name        = pyqtProperty(str, get_name, set_name, notify=name_changed)
    extensions  = pyqtProperty(dict, get_extensions)

def make_device_config(bus, address, idc, name=str(), device_profile=None):
    if device_profile is not None and device_profile.idc != idc:
        raise ValueError("idc does not match device profile idc")

    ret = Device(bus, address, idc)
    ret.name = name

    if device_profile is not None:
        pps = filter(lambda pp: pp.should_be_stored(), device_profile.get_parameters())
        for pp in pps:
            ret.set_parameter(pp.address, pp.default)

        for name, value in device_profile.get_extensions():
            ret.set_extension(name, value)

    ret.modified = False

    return ret
