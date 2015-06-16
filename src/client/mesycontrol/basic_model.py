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

# TODO: add value range but take negative values returned by the MRC command
# line into account

BUS_RANGE   = xrange(2)
DEV_RANGE   = xrange(16)
PARAM_RANGE = xrange(256)
ALL_DEVICE_ADDRESSES = [(bus, dev) for bus in BUS_RANGE for dev in DEV_RANGE]

class MRCRegistry(QtCore.QObject):
    """Manages MRC instances"""

    mrc_added   = pyqtSignal(object)
    mrc_about_to_be_removed = pyqtSignal(object)
    mrc_removed = pyqtSignal(object)

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

    def __len__(self):
        return len(self._mrcs)

    def __iter__(self):
        return iter(self._mrcs)

    mrcs = pyqtProperty(list, lambda self: self.get_mrcs())

class MRC(QtCore.QObject):
    url_changed     = pyqtSignal(str)
    device_added    = pyqtSignal(object)
    device_about_to_be_removed = pyqtSignal(object)
    device_removed  = pyqtSignal(object)

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

    def add_device(self, device):
        if self.get_device(device.bus, device.address) is not None:
            raise ValueError("Device at (%d, %d) exists", device.bus, device.address)

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

    def __iter__(self):
        return iter(self._devices)

    url = pyqtProperty(str,
            fget=lambda self: self.get_url(),
            fset=lambda self, v: self.set_url(v),
            notify=url_changed)

class ReadResult(collections.namedtuple("ReadResult", "bus device address value")):
    """The result type for a read operation. A namedtuple with added conversion to int."""
    def __int__(self):
        return self.value

class SetResult(collections.namedtuple("SetResult", ReadResult._fields + ('requested_value',))):
    """The result type for a set operation. Adds requested_value to the fields
    of ReadResult. A namedtuple with added conversion to int."""
    def __int__(self):
        return self.value

class ResultFuture(future.Future):
    """
    Future subclass used to hold ReadResult/SetResult instances. This class
    adds an int() conversion method to easily obtain the result value.
    """
    def __int__(self):
        return int(self.result())

class Device(QtCore.QObject):
    bus_changed         = pyqtSignal(int)
    address_changed     = pyqtSignal(int)
    idc_changed         = pyqtSignal(int)
    mrc_changed         = pyqtSignal(object)
    parameter_changed   = pyqtSignal(int, object)   #: address, value

    def __init__(self, bus=None, address=None, idc=None, parent=None):
        super(Device, self).__init__(parent)
        self._bus       = int(bus) if bus is not None else None
        self._address   = int(address) if address is not None else None
        self._idc       = int(idc) if idc is not None else None
        self._mrc       = None
        self._memory    = dict()

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
        if self.has_cached_parameter(address):
            result = ReadResult(self.bus, self.address, address,
                    self.get_cached_parameter(address))
            return ResultFuture().set_result(result)

        return self.read_parameter(address)

    def read_parameter(self, address):
        """Read a parameter from the device.
        Subclass implementations must call Device.set_cached_parameter() on
        read success to update the local memory cache.
        This method is expected to return a ResultFuture whose result is a
        ReadResult instance.
        """
        raise NotImplementedError()

    def set_parameter(self, address, value):
        """Set the parameter at the given address to the given value.
        Subclasses must call Device.set_cached_parameter() on success to update
        the local memory cache with the newly set value.
        This method is expected to return a ResultFuture whose result is a
        SetResult instance.
        """
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
        """Returns the memory cache in the form of a dict."""
        return dict(self._memory)

    # Using lambdas here to allow overriding property accessors.
    bus     = pyqtProperty(int,
            fget=lambda self: self.get_bus(),
            fset=lambda self, v: self.set_bus(v),
            notify=bus_changed)

    address = pyqtProperty(int,
            fget=lambda self: self.get_address(),
            fset=lambda self, v: self.set_address(v),
            notify=address_changed)

    idc     = pyqtProperty(int,
            fget=lambda self: self.get_idc(),
            fset=lambda self, v: self.set_idc(v),
            notify=idc_changed)

    mrc     = pyqtProperty(object,
            fget=lambda self: self.get_mrc(),
            fset=lambda self, v: self.set_mrc(v),
            notify=mrc_changed)