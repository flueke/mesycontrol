#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from nose.tools import assert_raises
from mesycontrol.hw_model import *

def test_set_scanbus_data_creates_devices():
    scanbus_data = [(0, 0) for i in range(16)]
    scanbus_data[0] = (17, 1)
    scanbus_data[2] = (21, 0)

    mrc = MRCModel()

    for bus in range(2):
        for addr in range(16):
            assert not mrc.has_device(bus, addr)

    mrc.set_scanbus_data(0, scanbus_data)

    for i in range(16):
        if scanbus_data[i][0] > 0:
            assert mrc.has_device(0, i)
            assert mrc.get_device(0, i).idc == scanbus_data[i][0]
            assert mrc.get_device(0, i).mrc == mrc
        else:
            assert not mrc.has_device(0, i)
        assert not mrc.has_device(1, i)


def test_set_scanbus_sets_address_conflict():
    scanbus_data = [(0, 0) for i in range(16)]
    scanbus_data[15] = (21, 2)

    mrc = MRCModel()
    mrc.set_scanbus_data(0, scanbus_data)

    assert mrc.has_device(0, 15)
    assert mrc.get_device(0, 15).idc == scanbus_data[15][0]
    assert mrc.get_device(0, 15).has_address_conflict()

def test_add_duplicate_device_raises():
    mrc = MRCModel()
    device_model_1 = DeviceModel(bus=0, address=0, idc=1, rc=True)
    device_model_2 = DeviceModel(bus=0, address=0, idc=1, rc=True)
    mrc.add_device(device_model_1)
    assert_raises(RuntimeError, mrc.add_device, device_model_2)

def test_set_scanbus_data_removes_device():
    scanbus_data = [(0, 0) for i in range(16)]
    scanbus_data[0] = (17, 1)

    mrc = MRCModel()
    mrc.set_scanbus_data(0, scanbus_data)

    assert mrc.has_device(0, 0)
    device = mrc.get_device(0, 0)
    assert device.mrc == mrc

    scanbus_data = [(0, 0) for i in range(16)]
    mrc.set_scanbus_data(0, scanbus_data)

    assert not mrc.has_device(0, 0)
    assert device.mrc is None
