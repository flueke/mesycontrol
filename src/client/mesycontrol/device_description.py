#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

class InvalidAttribute(RuntimeError):
    pass

class MissingAttribute(RuntimeError):
    pass

class ParameterDescription(object):
    def __init__(self):
        self.address = None     #: Numeric address of the parameter.
        self.name = None        #: Human readable name.
        self.poll = False       #: True if this parameter should be polled repeatedly.
        self.read_only = False  #: True if this parameter is read only.
        self.critical = False   #: True if this parameter affects a critical
                                #  device setting (e.g. MHV4 channel enable).
        self.safe_value = 0     #: Optional safe value if this parameter is critical.

    @staticmethod
    def fromDict(d):
        ret = ParameterDescription()
        for k, v in d.iteritems():
            if not hasattr(ret, k):
                raise InvalidAttribute(k)
            setattr(ret, k, v)
        return ret;

class DeviceDescription(object):
    def __init__(self):
        self.idc  = None        #: Device Identifier Code
        self.name = None        #: Device name (e.g. MHV4). Should be unique.
        self.parameters = []    #: List of ParameterDescription objects
        self._name2param = {}
        self._address2param = {}

    def add_parameter(self, param):
        self.parameters.append(param)
        self._name2param[param.name] = param
        self._address2param[param.address] = param

    def del_parameter(self, param):
        if param in self.parameters:
            self.parameters.remove(param)
            del self._name2param[param.name]
            del self._address2param[param.address]

    def get_parameter_by_name(self, name):
        return self._name2param.get(name, None)

    def get_parameter_by_address(self, address):
       return self._address2param.get(address, None)

    def get_critical_parameters(self):
       return [p for p in self.parameters if p.critical]

    @staticmethod
    def fromDict(d):
        try:
            ret = DeviceDescription()
            ret.name = d['name']
            ret.idc  = int(d['idc'])
            for pd in d['parameters']:
                ret.add_parameter(ParameterDescription.fromDict(pd))
            return ret
        except KeyError as e:
            raise MissingAttribute(e.message)

