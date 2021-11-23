#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2016 mesytec GmbH & Co. KG <info@mesytec.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

__author__ = 'Florian Lüke'
__email__  = 'f.lueke@mesytec.com'

from mesycontrol.qt import Property
from mesycontrol.qt import Signal
from mesycontrol.qt import QtCore

import collections
import copy
import weakref

from mesycontrol import future
import mesycontrol.util as util


BUS_RANGE   = range(2)     # Valid bus numbers
DEV_RANGE   = range(16)    # Valid device addresses
PARAM_RANGE = range(256)   # Valid parameter addresses
SET_VALUE_MIN = 0           # minimum settable parameter value
SET_VALUE_MAX = 65535       # maximum settable parameter value
# Note: read values are in range (-32767, 32768) as the MRC displays larger
# values as negative numbers (a feature implemented for MHV-4 voltage output).

# List of valid bus and device address pairs
ALL_DEVICE_ADDRESSES = [(bus, dev) for bus in BUS_RANGE for dev in DEV_RANGE]

# Display and write modes for devices and device guis
HARDWARE, CONFIG, COMBINED = range(3)

class IDCConflict(RuntimeError):
    pass

class MRCRegistry(QtCore.QObject):
    """Manages MRC instances"""

    mrc_added   = Signal(object)
    mrc_about_to_be_removed = Signal(object)
    mrc_removed = Signal(object)

    def __init__(self, parent=None):
        super(MRCRegistry, self).__init__(parent)
        self._mrcs = list()
        self.log   = util.make_logging_source_adapter(__name__, self)

    def add_mrc(self, mrc):
        if self.get_mrc(mrc.url) is not None:
            raise ValueError("MRC '%s' exists" % mrc.url)

        self.log.debug("add_mrc: %s %s", mrc, mrc.url)
        self._mrcs.append(mrc)
        self._mrcs.sort(key=lambda mrc: mrc.url)
        self.mrc_added.emit(mrc)

    def remove_mrc(self, mrc):
        try:
            if mrc not in self._mrcs:
                raise ValueError()
            self.mrc_about_to_be_removed.emit(mrc)
            self._mrcs.remove(mrc)
            self.mrc_removed.emit(mrc)
        except ValueError:
            raise ValueError("No such MRC %s" % mrc)

    def get_mrc(self, url):
        return next((mrc for mrc in self._mrcs if mrc.url == url), None)

    def get_mrcs(self):
        return list(self._mrcs)

    def contains_devices(self):
        return any((len(mrc) for mrc in self))

    def __len__(self):
        return len(self._mrcs)

    def __nonzero__(self):
        return self is not None

    def __iter__(self):
        return iter(self._mrcs)

    mrcs = Property(list, lambda self: self.get_mrcs())

class MRC(QtCore.QObject):
    url_changed     = Signal(str)
    device_added    = Signal(object)
    device_about_to_be_removed = Signal(object)
    device_removed  = Signal(object)

    def __init__(self, url, parent=None):
        super(MRC, self).__init__(parent)
        self.log        = util.make_logging_source_adapter(__name__, self)
        self._url       = str(url)
        self._devices   = list()

    def set_url(self, url):
        if self._url != url:
            self._url = str(url)
            self.url_changed.emit(self.url)
            return True

    def get_url(self):
        return self._url

    def get_display_url(self):
        return util.display_url(self.url)

    def add_device(self, device):
        if self.get_device(device.bus, device.address) is not None:
            raise ValueError("Device at (%d, %d) exists" % (device.bus, device.address))

        self.log.debug("add_device: %s", device)

        self._devices.append(device)
        self._devices.sort(key=lambda device: (device.bus, device.address))
        device.mrc = self
        self.device_added.emit(device)
        return True

    def remove_device(self, device):
        try:
            if device not in self._devices:
                raise ValueError()
            self.device_about_to_be_removed.emit(device)
            self._devices.remove(device)
            device.mrc = None
            self.log.debug("remove_device: %s", device)
            self.device_removed.emit(device)
            return True
        except ValueError:
            raise ValueError("No Device %s" % device)

    def get_device(self, bus, address):
        compare = lambda d: (d.bus, d.address) == (bus, address)
        return next((dev for dev in self._devices if compare(dev)), None)
    
    def get_devices(self, bus=None):
        if bus is None:
            return list(self._devices)
        return [d for d in self._devices if d.bus == bus]

    def has_device(self, bus, address):
        return self.get_device(bus, address) is not None

    def __len__(self):
        return len(self._devices)

    def __nonzero__(self):
        return self is not None

    def __iter__(self):
        return iter(self._devices)

    url = Property(str,
            fget=lambda self: self.get_url(),
            fset=lambda self, v: self.set_url(v),
            notify=url_changed)

class ReadResult(collections.namedtuple("ReadResult", "bus device address value")):
    """The result type for a read operation. A namedtuple with added conversion to int."""
    def __int__(self):
        return self.value

class SetResult(collections.namedtuple("SetResult", ReadResult._fields + ('requested_value',))):
    """The result type for a set operation.
    Adds requested_value to the fields of ReadResult and conversions to int and
    bool. The bool conversion returns True if value equals requested value.
    """
    def __int__(self):
        return self.value

    def __nonzero__(self):
        return self.value == self.requested_value

class ResultFuture(future.Future):
    """
    Future subclass used to hold ReadResult/SetResult instances. This class
    adds an int() conversion method to easily obtain the result value.
    """
    def __int__(self):
        return int(self.result())

class Device(QtCore.QObject):
    bus_changed         = Signal(int)
    address_changed     = Signal(int)
    idc_changed         = Signal(int)
    mrc_changed         = Signal(object)
    parameter_changed   = Signal(int, object)   #: address, value
    memory_about_to_be_cleared = Signal(object) #: memory
    memory_cleared = Signal()

    extension_added     = Signal(str, object)
    extension_changed   = Signal(str, object)
    extension_removed   = Signal(str, object)

    def __init__(self, bus=None, address=None, idc=None, parent=None):
        super(Device, self).__init__(parent)
        self.log        = util.make_logging_source_adapter(__name__, self)
        self._bus       = int(bus) if bus is not None else None
        self._address   = int(address) if address is not None else None
        self._idc       = int(idc) if idc is not None else None
        self._mrc       = None
        self._memory    = dict() # address -> value
        self._read_futures = dict() # address -> future
        self._extensions = dict() # name -> value

    def get_bus(self):
        """Returns the devices bus number."""
        return self._bus

    def set_bus(self, bus):
        """Set the devices bus number. Bus must be in BUS_RANGE."""
        if self.bus != bus:
            bus       = int(bus)
            if bus not in BUS_RANGE:
                raise ValueError("Bus out of range")
            self._bus = bus
            self.bus_changed.emit(self.bus)
            return True

    def get_address(self):
        """Get the devices address on the bus."""
        return self._address

    def set_address(self, address):
        """Set the devices address. address must be within DEV_RANGE."""
        if self.address != address:
            address       = int(address)
            if address not in DEV_RANGE:
                raise ValueError("Device address out of range")
            self._address = address
            self.address_changed.emit(self.address)
            return True

    def get_idc(self):
        """Get the devices identifier code."""
        return self._idc

    def set_idc(self, idc):
        """Set the devices identifier code."""
        if self.idc != idc:
            self._idc = int(idc)
            self.idc_changed.emit(self.idc)
            return True

    def get_mrc(self):
        """Get the MRC the device is connected to. Returns None if no MRC has
        been set."""
        return None if self._mrc is None else self._mrc()

    def set_mrc(self, mrc):
        """Set the MRC the device is connected to. Pass None to clear the
        current MRC."""
        if self.mrc != mrc:
            self._mrc = None if mrc is None else weakref.ref(mrc)
            self.mrc_changed.emit(self.mrc)
            return True

    def get_parameter(self, address):
        """Get a parameter from the devices memory cache if available.
        Otherwise use Device.read_parameter() to read the parameter from the
        hardware.
        Returns a ResultFuture whose result is a ReadResult instance.
        """
        # Return from the cache if available.
        if self.has_cached_parameter(address):
            result = ReadResult(self.bus, self.address, address,
                    self.get_cached_parameter(address))
            return ResultFuture().set_result(result)

        # Return the future of a pending read.
        if address in self._read_futures:
            return self._read_futures[address]

        # Neither cached nor read in progress -> start a read
        return self.read_parameter(address)

    def read_parameter(self, address):
        """Read a parameter from the device.
        This method returns a ResultFuture whose result is a ReadResult
        instance.
        On read success the local memory cache is updated with the newly read
        value.
        """
        # Update cache on read success
        def on_parameter_read(f):
            if f.exception() is None:
                self.set_cached_parameter(address, int(f))

        ret = self._read_parameter(address).add_done_callback(on_parameter_read)

        # Store future to satisfy get_parameter() requests while the read is in
        # progress.
        if address not in self._read_futures:
            def done(f):
                del self._read_futures[address]

            self._read_futures[address] = ret
            ret.add_done_callback(done)

        return ret

    def _read_parameter(self, address):
        """Read implementation. Subclasses must return a ResultFuture whose
        result is a ReadResult object."""
        raise NotImplementedError()

    def set_parameter(self, address, value):
        """Set the parameter at the given address to the given value.
        Updates the local memory cache on success.
        This method returns a ResultFuture whose result is a SetResult
        instance.
        """
        def on_parameter_set(f):
            if not f.cancelled() and f.exception() is None:
                self.set_cached_parameter(address, int(f))

        ret = self._set_parameter(address, value)
        ret.add_done_callback(on_parameter_set)
        return ret

    def _set_parameter(self, address, value):
        """Set implementation. Subclasses must return a ResultFuture whose
        result is a SetResult instance."""
        raise NotImplementedError()

    def get_cached_parameter(self, address):
        """Returns the integer value of the cached parameter at the given
        address or None if the parameter is not present in the cache.
        address must be within PARAM_RANGE, otherwise a ValueError will be
        raised."""
        if address not in PARAM_RANGE:
            raise ValueError("Parameter address out of range")

        return self._memory.get(address, None)

    def set_cached_parameter(self, address, value):
        """Set the memory cache at the given address to the given value.
        Emits parameter_changed and returns True if the value changes.
        Otherwise no signal is emitted and False is returned.
        Raises ValueError if address is out of range."""

        if address not in PARAM_RANGE:
            raise ValueError("Parameter address out of range")

        value = int(value)
        if self.get_cached_parameter(address) != value:
            self._memory[address] = value
            self.parameter_changed.emit(address, value)
            return True

        return False

    def clear_cached_parameter(self, address):
        """Removes the cached memory value at the given address.
        Emits parameter_changed and returns True if the parameter was present
        in the memory cache. Otherwise False is returned."""
        if self.has_cached_parameter(address):
            del self._memory[address]
            self.parameter_changed.emit(address, None)
            return True

        return False

    def has_cached_parameter(self, address):
        """Returns True if the given address is in the memory cache."""
        return address in self._memory

    def get_cached_memory(self):
        """Returns a copy of the memory cache in the form of a dict."""
        return dict(self._memory)

    def get_cached_memory_ref(self):
        """Returns a reference to the memory cache (a dictionary)."""
        return self._memory

    def clear_cached_memory(self):
        """Clears the memory cache.
        Returns True if any parameters where cleared. Otherwise False is
        returned. """
        self.memory_about_to_be_cleared.emit(self.get_cached_memory())
        ret = False
        for address in sorted(self._memory.keys()):
            if self.clear_cached_parameter(address):
                ret = True
        self.memory_cleared.emit()
        return ret

    def set_extension(self, name, value):
        is_new    = name not in self._extensions
        cur_value = self._extensions.get(name, None)

        if cur_value != value:
            self.log.debug("extension %s changes from %s to %s (is_new=%s)",
                    name, cur_value, value, is_new)

            self._extensions[name] = value
            if is_new:
                self.extension_added.emit(name, value)
            self.extension_changed.emit(name, value)
            return True
        return False

    def has_extension(self, name):
        return name in self._extensions

    def get_extension(self, name):
        # Return a copy here as otherwise modifications to list and dict values
        # would modify the extension store directly without set_extension being
        # used. Thus the modified flag of configs would not be set.
        return copy.deepcopy(self._extensions[name])

    def get_extensions(self):
        return dict(self._extensions)

    def remove_extension(self, name):
        value = self.get_extension(name)
        del self._extensions[name]
        self.extension_removed.emit(name, value)
        return True

    # Using lambdas here to allow overriding property accessors.
    bus     = Property(int,
            fget=lambda self: self.get_bus(),
            fset=lambda self, v: self.set_bus(v),
            notify=bus_changed)

    address = Property(int,
            fget=lambda self: self.get_address(),
            fset=lambda self, v: self.set_address(v),
            notify=address_changed)

    idc     = Property(int,
            fget=lambda self: self.get_idc(),
            fset=lambda self, v: self.set_idc(v),
            notify=idc_changed)

    mrc     = Property(object,
            fget=lambda self: self.get_mrc(),
            fset=lambda self, v: self.set_mrc(v),
            notify=mrc_changed)

    extensions = Property(dict,
            fget=lambda self: self.get_extensions())
