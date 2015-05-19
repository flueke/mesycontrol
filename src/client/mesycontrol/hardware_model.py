#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtProperty

import basic_model as bm

class MRC(bm.MRC):
    def __init__(self, url, parent=None):
        super(MRC, self).__init__(url, parent)

class Device(bm.Device):
    def __init__(self, bus, address, idc, parent=None):
        super(Device, self).__init__(bus, address, idc, parent)

    def read_parameter(self, address):
        """Reads the given device address."""
        return self.controller.read_parameter(self.bus, self.address, address)

    def set_parameter(self, address, value):
        """Sets the given device address to the given value."""
        return self.controller.set_parameter(self, self.bus, self.address, address, value)

    def get_controller(self):
        return self.mrc.controller

    controller = pyqtProperty(object, get_controller)
