#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
import functools

class DuplicateParameter(RuntimeError):
    pass

class Unit(object):
    def __init__(self, label, factor=1.0, offset=0.0, name=None):
        if label is None and name is None:
            raise RuntimeError("Neither `label' nor `name' given.")

        self.label  = str(label) if label is not None else None
        self.name   = str(name) if name is not None else self.label
        self.factor = float(factor) #: Factor used for value<->unit conversion.
        self.offset = float(offset) #: Offset used for value<->unit conversion.

        if self.factor == 0.0:
            raise RuntimeError("invalid unit conversion factor of 0.0 given")

    def unit_value(self, raw_value):
        return raw_value / self.factor + self.offset

    def raw_value(self, unit_value):
        return round((unit_value - self.offset) * self.factor)

    def get_factor(self):
        return self._factor

    def set_factor(self, factor):
        self._factor = float(factor)

    def get_offset(self):
        return self._offset

    def set_offset(self, offset):
        self._offset = float(offset)

    factor = property(get_factor, set_factor)
    offset = property(get_offset, set_offset)

    @staticmethod
    def fromDict(d):
        label = d.get('label', None)
        name  = d.get('name', None)
        ret   = Unit(name=name, label=label)
        if 'factor' in d: ret.factor = d['factor']
        if 'offset' in d: ret.offset = d['offset']
        return ret
        
raw_unit = Unit(label=None, name='raw', factor=1.0, offset=0.0)

class Range(object):
    def __init__(self, min_value, max_value):
        self.min_value = min_value
        self.max_value = max_value

    def in_range(self, value):
        return self.min_value <= value and value <= self.max_value

    def limit_to(self, value):
        if value < self.min_value:
            return self.min_value

        if value > self.max_value:
            return self.max_value

        return value

    def to_tuple(self):
        return (self.min_value, self.max_value)

    def __getitem__(self, key):
        if key == 0:
            return self.min_value

        if key == 1:
            return self.max_value

        raise KeyError(key)

@functools.total_ordering
class ParameterProfile(object):
    def __init__(self, address):
        self.address        = int(address)      #: Numeric address of the parameter.
        self._name          = None              #: Human readable name.
        self.index          = None              #: Index number of this parameter if it is part of a sequence
                                                #: of parameters. E.g.: for MHV4 channels 1 through 4 index numbers
                                                #: would be 0 through 3.
        self.poll           = False             #: True if this parameter should be polled repeatedly.
        self.read_only      = False             #: True if this parameter is read only. Its
                                                #  value will not be stored in the configuration.
        self.critical       = False             #: True if this parameter affects a critical
                                                #  device setting (e.g. MHV4 channel enable).
                                                #  Only meaningful for writeable parameters.
        self.safe_value     = 0                 #: Optional safe value if this parameter is critical.
        self.do_not_store   = False             #: True if this parameters value should not be stored
                                                #  in or loaded from the configuration (e.g. MSCF-16
                                                #  copy function).
        self.range          = None              #: Range instance limiting this parameters values.
        self.units          = list()            #: Optional list of Unit definitions for this parameter.
                                                #: Used to convert between raw and human readable parameter
                                                #: values.

        self._default       = None              #: Default value of the parameter. If not set the minimum of the
                                                #  parameters range will be used. If no range is set defaults to 0.

        self.units.append(raw_unit)

    def should_be_stored(self):
        return not self.read_only and not self.do_not_store

    def is_named(self):
        return self._name is not None and len(self._name)

    def get_name(self):
        if not self.is_named():
            return str()

        return self._name

    def set_name(self, name):
        self._name = str(name) if name is not None else None

    def get_unit(self, label_or_name):
        return filter(lambda u: u.label == label_or_name or u.name == label_or_name, self.units)[0]

    def has_index(self):
        return self.index is not None

    def set_default(self, value):
        self._default = int(value)

    def get_default(self):
        if self._default is not None:
            return self._default

        if self.range is not None:
            return self.range.min_value

        return 0

    def __eq__(self, o):
        if isinstance(o, int):
            return self.address == o
        return self.address == o.address

    def __lt__(self, o):
        if isinstance(o, int):
            return self.address < o
        return self.address < o.address

    def __str__(self):
        if self.is_named():
            return "ParameterProfile(address=%d, name=%s)" % (self.address, self.name)
        return "ParameterProfile(address=%d)" % self.address

    name = property(get_name, set_name)
    default = property(get_default, set_default)

    @staticmethod
    def fromDict(d):
        ret = ParameterProfile(d['address'])
        #if 'name' in d: ret.name = d['name']
        #if 'index' in d: ret.index = int(d['index'])
        #if 'poll' in d: ret.poll = bool(d['poll'])
        #if 'read_only' in d: ret.read_only = bool(d['read_only'])
        #if 'critical' in d: ret.critical = bool(d['critical'])
        #if 'safe_value' in d: ret.safe_value = int(d['safe_value'])
        #if 'do_not_store' in d: ret.do_not_store = bool(d['do_not_store'])


        attributes = (a for a in d.keys() if a not in ('address', 'range', 'units'))

        for attr in attributes:
            setattr(ret, attr, d[attr])

        if 'range' in d: ret.range = Range(d['range'][0], d['range'][1])
        if 'units' in d:
            for unit_def in d['units']:
                ret.units.append(Unit.fromDict(unit_def))

        return ret;


# TODO: add get_poll_items() and use it for polling instead of get_volatile_addresses().
# difference: get_poll_items() returns a combination of single parameters and
# parameter ranges whereas get_volatile_addresses() returns a list of parameter
# addresses
class DeviceProfile(object):
    def __init__(self, idc):
        self.idc        = int(idc)  #: Device Identifier Code
        self.name       = None      #: Device name (e.g. MHV4). Should be unique.
        self.parameters             = list()
        self.address_parameter_map  = dict()
        self.name_parameter_map     = dict()
        self._extensions            = dict()

    def __str__(self):
        return "DeviceProfile(name=%s, idc=%d)" % (self.name, self.idc)

    def add_parameter(self, param):
        if param.address in self.address_parameter_map:
            raise DuplicateParameter("Address %d already present in DeviceProfile %s" %
                    (param.address, self))

        self.parameters.append(param)
        self.address_parameter_map[param.address] = param
        self.name_parameter_map[param.name] = param

    def get_parameter_by_address(self, address):
        return self.address_parameter_map.get(address, None)

    def get_parameter_by_name(self, name):
        return self.name_parameter_map.get(name, None)

    def has_parameter(self, param):
        return (param in self.address_parameter_map or
                param in self.name_parameter_map)

    def __getitem__(self, key):
        if isinstance(key, (str, unicode, QtCore.QString)):
            return self.get_parameter_by_name(str(key))

        try:
            return self.get_parameter_by_address(int(key))
        except ValueError:
            raise KeyError(key)

    def get_parameters(self):
        return list(self.parameters)

    def get_critical_parameters(self):
        return filter(lambda p: p.critical, self.parameters)

    def get_non_critical_parameters(self):
        return filter(lambda p: not p.critical, self.parameters)

    def get_config_parameters(self):
        predicate = lambda p: not p.read_only and not p.do_not_store
        return filter(predicate, self.parameters)

    def get_non_critical_config_parameters(self):
        predicate = lambda p: not p.critical and not p.read_only and not p.do_not_store
        return filter(predicate, self.parameters)

    def get_static_addresses(self):
        return map(lambda p: p.address, filter(lambda p: not p.poll, self.parameters))

    def get_volatile_addresses(self):
        return map(lambda p: p.address, filter(lambda p: p.poll, self.parameters))

    def set_extension(self, ext):
        #d = dict()
        #d['name'] = name = ext['name']
        #d['default'] = ext['value']

        #if 'limits' in ext:
        #    d['limits'] = ext['limits']

        #if 'values' in ext:
        #    d['values'] = ext['values']

        #self._extensions[name] = d
        # FIXME: change extension mechanism to handle extension meta data
        # => stored extension values in config are different from extension
        # definitions in the device profile.
        self._extensions[ext['name']] = ext['value']

    def get_extension(self, name):
        return self._extensions[name]

    def get_extensions(self):
        return dict(self._extensions)

    def get_parameter_names(self):
        return dict((pp.address, pp.name)
                for pp in filter(lambda pp: pp.is_named(), self.parameters))

def from_dict(d):
    ret = DeviceProfile(d['idc'])
    ret.name = str(d.get('name', None))

    for pd in d.get('parameters', list()):
        ret.add_parameter(ParameterProfile.fromDict(pd))

    for ext in d.get('extensions', list()):
        ret.set_extension(ext)

    return ret


def make_generic_profile(device_idc):
    ret = DeviceProfile(device_idc)
    ret.name = "GenericDevice(idc=%d)" % device_idc

    for i in range(256):
        ret.add_parameter(ParameterProfile(i))

    return ret
