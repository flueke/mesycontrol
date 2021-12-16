#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2021 mesytec GmbH & Co. KG <info@mesytec.com>
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

from nose.tools import assert_raises
from .. import hardware_model as hm

#def test_set_scanbus_data_creates_devices():
#    scanbus_data = [(0, 0) for i in range(16)]
#    scanbus_data[0] = (17, 1)
#    scanbus_data[2] = (21, 0)
#
#    mrc = hm.HardwareMrc("/dev/ttyUSB0")
#
#    for bus in range(2):
#        for addr in range(16):
#            assert not mrc.has_device(bus, addr)
#
#    mrc.set_scanbus_data(0, scanbus_data)
#
#    for i in range(16):
#        if scanbus_data[i][0] > 0:
#            assert mrc.has_device(0, i)
#            assert mrc.get_device(0, i).idc == scanbus_data[i][0]
#            assert mrc.get_device(0, i).mrc == mrc
#        else:
#            assert not mrc.has_device(0, i)
#        assert not mrc.has_device(1, i)


#def test_set_scanbus_sets_address_conflict():
#    scanbus_data = [(0, 0) for i in range(16)]
#    scanbus_data[15] = (21, 2)
#
#    mrc = hm.HardwareMrc("/dev/ttyUSB0")
#    mrc.set_scanbus_data(0, scanbus_data)
#
#    assert mrc.has_device(0, 15)
#    assert mrc.get_device(0, 15).idc == scanbus_data[15][0]
#    assert mrc.get_device(0, 15).has_address_conflict()

def test_add_duplicate_device_raises():
    mrc = hm.HardwareMrc("/dev/ttyUSB0")
    device_model_1 = hm.Device(bus=0, address=0, idc=1)
    device_model_2 = hm.Device(bus=0, address=0, idc=1)
    mrc.add_device(device_model_1)
    assert_raises(ValueError, mrc.add_device, device_model_2)

#def test_set_scanbus_data_removes_device():
#    scanbus_data = [(0, 0) for i in range(16)]
#    scanbus_data[0] = (17, 1)
#
#    mrc = hm.HardwareMrc("/dev/ttyUSB0")
#    mrc.set_scanbus_data(0, scanbus_data)
#
#    assert mrc.has_device(0, 0)
#    device = mrc.get_device(0, 0)
#    assert device.mrc == mrc
#
#    scanbus_data = [(0, 0) for i in range(16)]
#    mrc.set_scanbus_data(0, scanbus_data)
#
#    assert not mrc.has_device(0, 0)
#    assert device.mrc is None
