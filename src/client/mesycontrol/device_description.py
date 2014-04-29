#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

class InvalidAttribute(RuntimeError):
    pass

class MissingAttribute(RuntimeError):
    pass

class DuplicateParameter(RuntimeError):
    pass

class ParameterDescription(object):
    def __init__(self, address):
        self.address = int(address) #: Numeric address of the parameter.
        self.name = None            #: Human readable name.
        self.poll = False           #: True if this parameter should be polled repeatedly.
        self.read_only = False      #: True if this parameter is read only.
        self.critical = False       #: True if this parameter affects a critical
                                    #  device setting (e.g. MHV4 channel enable).
        self.safe_value = 0         #: Optional safe value if this parameter is critical.

    def __eq__(self, o):
        return self.address == o.address \
                and self.name == o.name \
                and self.poll == o.poll \
                and self.read_only == o.read_only \
                and self.critical == o.critical \
                and self.safe_value == o.safe_value

    def __ne__(self, o):
        return not (self == o)

    @staticmethod
    def fromDict(d):
        ret = ParameterDescription(d['address'])
        for k, v in d.iteritems():
            if not hasattr(ret, k):
                raise InvalidAttribute(k)
            setattr(ret, k, v)
        return ret;

class DeviceDescription(object):
    def __init__(self, idc):
        self.idc  = int(idc)        #: Device Identifier Code
        self.name = None            #: Device name (e.g. MHV4). Should be unique.
        self.parameters = {}        #: Maps ParameterDescription.address to ParameterDescription

    def __eq__(self, o):
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
            raise DuplicateParameter("Address %d already present in DeviceDescription" % param.address)

        self.parameters[param.address] = param

    def del_parameter(self, param):
        if param in self.parameters.values():
            del self.parameters[param.address]

    def del_parameter_by_address(self, address):
        if address in self.parameters:
            del self.parameters[address]

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
        try:
            ret = DeviceDescription(d['idc'])
            ret.name = str(d.get('name', None))
            for pd in d['parameters']:
                ret.add_parameter(ParameterDescription.fromDict(pd))
            return ret
        except KeyError as e:
            raise MissingAttribute(e.message)


    @staticmethod
    def makeGenericDescription(device_idc):
        ret = DeviceDescription(device_idc)
        for i in range(256):
            ret.add_parameter(ParameterDescription(i))

        return ret
