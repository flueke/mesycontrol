#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

class DuplicateParameter(RuntimeError):
    pass

class Unit(object):
    def __init__(self, unit_label, factor=1.0, offset=0.0):
        self.label  = str(unit_label)
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
        ret = Unit(d['label'])
        if 'factor' in d: ret.factor = d['factor']
        if 'offset' in d: ret.offset = d['offset']
        return ret
        
raw_unit = Unit('raw', 1.0, 0.0)

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

class ParameterProfile(object):
    def __init__(self, address):
        self.address        = int(address)      #: Numeric address of the parameter.
        self._name          = None              #: Human readable name.
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

        self.units.append(raw_unit)

    def should_be_stored(self):
        return not self.read_only and not self.do_not_store

    def is_named(self):
        return self._name is not None and len(self._name)

    def get_name(self):
        if not self.is_named():
            return None

        return self._name

    def set_name(self, name):
        self._name = str(name) if name is not None else None

    def get_unit(self, label):
        return filter(lambda u: u.label == label, self.units)[0]

    def __eq__(self, o):
        return (self.address == o.address
                and self.name == o.name
                and self.poll == o.poll
                and self.read_only == o.read_only
                and self.critical == o.critical
                and self.safe_value == o.safe_value
                and self.do_not_store == o.do_not_store
                and self.value_range == o.value_range
                and self.unit == o.unit)

    def __ne__(self, o):
        return not (self == o)

    def __str__(self):
        if self.is_named():
            return "ParameterProfile(address=%d, name=%s)" % (self.address, self.name)
        return "ParameterProfile(address=%d)" % self.address

    name = property(get_name, set_name)

    @staticmethod
    def fromDict(d):
        ret = ParameterProfile(d['address'])
        if 'name' in d: ret.name = d['name']
        if 'poll' in d: ret.poll = bool(d['poll'])
        if 'read_only' in d: ret.read_only = bool(d['read_only'])
        if 'critical' in d: ret.critical = bool(d['critical'])
        if 'safe_value' in d: ret.safe_value = int(d['safe_value'])
        if 'do_not_store' in d: ret.do_not_store = bool(d['do_not_store'])
        if 'range' in d: ret.range = Range(d['range'][0], d['range'][1])
        if 'units' in d:
            for unit_def in d['units']:
                ret.units.append(Unit.fromDict(unit_def))

        return ret;


class DeviceProfile(object):
    def __init__(self, idc):
        self.idc        = int(idc)  #: Device Identifier Code
        self.name       = None      #: Device name (e.g. MHV4). Should be unique.
        self.parameters = dict()    #: Maps ParameterProfile.address to ParameterProfile

    def __str__(self):
        return "DeviceProfile(name=%s, idc=%d)" % (self.name, self.idc)

    def __eq__(self, o):
        if o is None:
            return False

        if self.idc != o.idc or self.name != o.name:
            return False

        if len(self.parameters) != len(o.parameters):
            return False

        for address, param in self.parameters.iteritems():
            if param != o.parameters.get(address, None):
                return False

        return True

    def __ne__(self, o):
        return not (self == o)

    def add_parameter(self, param):
        if param.address in self.parameters:
            raise DuplicateParameter("Address %d already present in DeviceProfile %s" %
                    (param.address, self))

        self.parameters[param.address] = param

    def get_parameter_by_address(self, address):
        return self.parameters.get(address, None)

    def get_parameter_by_name(self, name):
        try:
            return filter(lambda p: p.name == name, self.parameters.values())[0]
        except IndexError:
            return None

    def get_parameters(self):
        return self.parameters.values()

    def get_critical_parameters(self):
        return filter(lambda p: p.critical, self.parameters.values())

    def get_non_critical_parameters(self):
        return filter(lambda p: not p.critical, self.parameters.values())

    @staticmethod
    def fromDict(d):
        ret = DeviceProfile(d['idc'])
        ret.name = str(d.get('name', None))
        for pd in d['parameters']:
            ret.add_parameter(ParameterProfile.fromDict(pd))
        return ret


def make_generic_profile(device_idc):
    ret = DeviceProfile(device_idc)
    ret.name = "GenericDevice(idc=%d)" % device_idc

    for i in range(256):
        ret.add_parameter(ParameterProfile(i))

    return ret
