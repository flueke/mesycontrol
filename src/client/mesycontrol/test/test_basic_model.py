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

import mock
from nose.tools import assert_raises

from .. import basic_model as bm

def test_create_mrc_registry():
    reg = bm.MRCRegistry()

    assert len(reg.mrcs) == 0

def test_add_mrc():
    reg = bm.MRCRegistry()

    reg.mrc_added = mock.MagicMock()
    reg.mrc_removed = mock.MagicMock()

    assert reg.get_mrc("foo") is None

    mrc = bm.MRC("the url")
    reg.add_mrc(mrc)

    assert len(reg.mrcs) == 1
    assert reg.get_mrc("the url") is mrc
    assert reg.get_mrc("foo") is None
    reg.mrc_added.emit.assert_called_once_with(mrc)
    assert reg.mrc_removed.emit.call_count == 0

    reg.mrc_added.reset_mock()

    mrc2 = bm.MRC("2nd")
    reg.add_mrc(mrc2)

    assert len(reg.mrcs) == 2
    assert reg.get_mrc("the url") is mrc
    assert reg.get_mrc("2nd") is mrc2
    assert reg.get_mrc("foo") is None
    reg.mrc_added.emit.assert_called_once_with(mrc2)
    assert reg.mrc_removed.call_count == 0

def test_remove_mrc():
    reg = bm.MRCRegistry()

    reg.mrc_removed = mock.MagicMock()

    mrc1 = bm.MRC("the url")
    mrc2 = bm.MRC("2nd")

    reg.add_mrc(mrc1)

    assert_raises(ValueError, reg.remove_mrc, mrc2)
    assert len(reg.mrcs) == 1

    reg.add_mrc(mrc2)

    assert len(reg.mrcs) == 2

    reg.remove_mrc(mrc1)
    assert len(reg.mrcs) == 1
    assert reg.get_mrc("the url") is None
    assert reg.get_mrc("2nd") is mrc2
    reg.mrc_removed.emit.assert_called_once_with(mrc1)
    assert_raises(ValueError, reg.remove_mrc, mrc1)

    reg.mrc_removed.reset_mock()

    reg.remove_mrc(mrc2)

    assert len(reg.mrcs) == 0
    assert reg.get_mrc("the url") is None
    assert reg.get_mrc("2nd") is None
    reg.mrc_removed.emit.assert_called_once_with(mrc2)
    assert_raises(ValueError, reg.remove_mrc, mrc1)
    assert_raises(ValueError, reg.remove_mrc, mrc2)

def test_add_device():
    mrc = bm.MRC("example.com")
    d1  = bm.Device(0, 0, 42)
    d2  = bm.Device(0, 15, 42)
    d3  = bm.Device(1, 0, 13)

    mrc.device_added = mock.MagicMock()

    mrc.add_device(d1)
    assert len(mrc.get_devices()) == 1
    assert len(mrc.get_devices(0)) == 1
    assert len(mrc.get_devices(1)) == 0
    assert mrc.get_device(0, 0) is d1
    assert mrc.get_device(0, 15) is None
    mrc.device_added.emit.assert_called_once_with(d1)
    mrc.device_added.reset_mock()

    mrc.add_device(d2)
    assert len(mrc.get_devices()) == 2
    assert len(mrc.get_devices(0)) == 2
    assert len(mrc.get_devices(1)) == 0
    assert mrc.get_device(0, 0) is d1
    assert mrc.get_device(0, 15) is d2
    mrc.device_added.emit.assert_called_once_with(d2)
    mrc.device_added.reset_mock()

    mrc.add_device(d3)
    assert len(mrc.get_devices()) == 3
    assert len(mrc.get_devices(0)) == 2
    assert len(mrc.get_devices(1)) == 1
    assert mrc.get_device(0, 0) is d1
    assert mrc.get_device(0, 15) is d2
    assert mrc.get_device(1, 0) is d3
    mrc.device_added.emit.assert_called_once_with(d3)
    mrc.device_added.reset_mock()

    d4 = bm.Device(1, 0, 500)
    assert_raises(ValueError, mrc.add_device, d4)
    assert len(mrc.get_devices()) == 3
    assert len(mrc.get_devices(0)) == 2
    assert len(mrc.get_devices(1)) == 1
    assert mrc.get_device(0, 0) is d1
    assert mrc.get_device(0, 15) is d2
    assert mrc.get_device(1, 0) is d3

def test_remove_device():
    mrc = bm.MRC("example.com")
    d1  = bm.Device(0, 0, 42)
    d2  = bm.Device(0, 15, 42)
    d3  = bm.Device(1, 0, 13)
    d4  = bm.Device(1, 0, 500)

    mrc.device_removed = mock.MagicMock()

    for d in (d1, d2, d3):
        mrc.add_device(d)

    assert len(mrc.get_devices()) == 3
    assert len(mrc.get_devices(0)) == 2
    assert len(mrc.get_devices(1)) == 1
    assert mrc.get_device(0, 0) is d1
    assert mrc.get_device(0, 15) is d2
    assert mrc.get_device(1, 0) is d3

    assert_raises(ValueError, mrc.remove_device, d4)

    mrc.remove_device(d2)
    assert len(mrc.get_devices()) == 2
    assert len(mrc.get_devices(0)) == 1
    assert len(mrc.get_devices(1)) == 1
    assert mrc.get_device(0, 0) is d1
    assert mrc.get_device(0, 15) is None
    assert mrc.get_device(1, 0) is d3
    assert_raises(ValueError, mrc.remove_device, d2)
    mrc.device_removed.emit.assert_called_once_with(d2)
    mrc.device_removed.reset_mock()

    mrc.remove_device(d1)
    assert len(mrc.get_devices()) == 1
    assert len(mrc.get_devices(0)) == 0
    assert len(mrc.get_devices(1)) == 1
    assert mrc.get_device(0, 0) is None
    assert mrc.get_device(0, 15) is None
    assert mrc.get_device(1, 0) is d3
    assert_raises(ValueError, mrc.remove_device, d1)
    assert_raises(ValueError, mrc.remove_device, d2)
    mrc.device_removed.emit.assert_called_once_with(d1)
    mrc.device_removed.reset_mock()

    mrc.remove_device(d3)
    assert len(mrc.get_devices()) == 0
    assert len(mrc.get_devices(0)) == 0
    assert len(mrc.get_devices(1)) == 0
    assert mrc.get_device(0, 0) is None
    assert mrc.get_device(0, 15) is None
    assert mrc.get_device(1, 0) is None
    assert_raises(ValueError, mrc.remove_device, d1)
    assert_raises(ValueError, mrc.remove_device, d2)
    assert_raises(ValueError, mrc.remove_device, d3)
    mrc.device_removed.emit.assert_called_once_with(d3)
    mrc.device_removed.reset_mock()

def test_device():
    d1 = bm.Device(1, 13, 42)
    d1.idc_changed = mock.MagicMock()
    d1.mrc_changed = mock.MagicMock()
    d1.parameter_changed = mock.MagicMock()

    assert d1.mrc is None
    assert d1.bus == 1
    assert d1.address == 13
    assert d1.idc == 42
    assert len(d1.get_cached_memory()) == 0
    for i in range(256):
        assert d1.get_cached_parameter(i) is None

    mrc    = bm.MRC("example.com")
    d1.mrc = mrc
    d1.mrc_changed.emit.assert_called_once_with(mrc)
    d1.mrc_changed.reset_mock()
    assert d1.mrc is mrc
    assert d1.bus == 1
    assert d1.address == 13
    assert d1.idc == 42
    assert len(d1.get_cached_memory()) == 0
    for i in range(256):
        assert d1.get_cached_parameter(i) is None

    d1.idc = 13
    d1.idc_changed.emit.assert_called_once_with(13)
    d1.idc_changed.reset_mock()
    assert d1.mrc is mrc
    assert d1.bus == 1
    assert d1.address == 13
    assert d1.idc == 13
    assert len(d1.get_cached_memory()) == 0
    for i in range(256):
        assert d1.get_cached_parameter(i) is None
        assert not d1.has_cached_parameter(i)

    d1.mrc = None
    d1.mrc_changed.emit.assert_called_once_with(None)
    d1.mrc_changed.reset_mock()
    assert d1.mrc is None
    assert d1.bus == 1
    assert d1.address == 13
    assert d1.idc == 13
    assert len(d1.get_cached_memory()) == 0
    for i in range(256):
        assert d1.get_cached_parameter(i) is None
        assert not d1.has_cached_parameter(i)


    d1.set_cached_parameter(0, 1234)
    assert d1.get_cached_parameter(0) == 1234
    assert d1.get_cached_memory()[0] == 1234
    assert d1.has_cached_parameter(0)
    assert len(d1.get_cached_memory()) == 1
    d1.parameter_changed.emit.assert_called_once_with(0, 1234)
    d1.parameter_changed.reset_mock()

    for i in range(256):
        d1.set_cached_parameter(i, i*i)
        assert d1.get_cached_parameter(i) == i*i
        assert d1.get_cached_memory()[i] == i*i
        assert d1.has_cached_parameter(i)
        rr = d1.get_parameter(i).result()
        assert rr.bus == d1.bus
        assert rr.device == d1.address
        assert rr.address == i
        assert rr.value == i*i
        d1.parameter_changed.emit.assert_called_once_with(i, i*i)
        d1.parameter_changed.reset_mock()
