#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import mock
from nose.tools import assert_raises

from .. import config_model as cm

def test_setup_basic():
    s = cm.Setup()

    assert not s.modified
    assert s.filename == str()

    s.filename_changed = mock.MagicMock()
    s.modified_changed = mock.MagicMock()

    # set filename
    s.filename = "test"

    s.filename_changed.emit.assert_called_once_with("test")
    s.modified_changed.emit.assert_called_once_with(True)

    assert s.modified
    assert s.filename == "test"

    # set modified
    s.modified_changed.reset_mock()
    s.modified = False
    assert not s.modified
    s.modified_changed.emit.assert_called_once_with(False)

    # set same filename
    s.filename_changed.reset_mock()
    s.modified_changed.reset_mock()

    s.filename = "test"

    assert not s.modified
    assert s.filename == "test"
    assert s.filename_changed.emit.call_count == 0
    assert s.modified_changed.emit.call_count == 0

def test_setup_mrc():
    s = cm.Setup()
    mrc = cm.MRC("the_url")

    s.modified_changed = mock.MagicMock()
    s.mrc_added = mock.MagicMock()
    s.mrc_removed = mock.MagicMock()

    # add mrc
    s.add_mrc(mrc)

    assert s.get_mrcs()[0] == mrc
    assert s.modified
    assert not mrc.modified
    s.modified_changed.emit.assert_called_once_with(True)
    s.mrc_added.emit.assert_called_once_with(mrc)
    assert s.mrc_removed.emit.call_count == 0

    # modify mrc should propagate to setup
    s.modified = False
    s.modified_changed.reset_mock()

    mrc.name = "my mrc"
    assert s.modified
    s.modified_changed.emit.assert_called_once_with(True)

    # set modified on setup -> should propagate to mrc
    s.modified = False
    assert not mrc.modified

    # remove mrc
    s.remove_mrc(mrc)
    assert s.modified
    s.mrc_removed.emit.assert_called_once_with(mrc)

def test_mrc_basic():
    mrc = cm.MRC("the_url")

    mrc.modified_changed = mock.MagicMock()
    mrc.name_changed = mock.MagicMock()

    assert not mrc.modified
    assert mrc.name == str()

    # set name
    mrc.name = "my mrc"

    assert mrc.name == "my mrc"
    assert mrc.modified
    mrc.modified_changed.emit.assert_called_once_with(True)
    mrc.name_changed.emit.assert_called_once_with("my mrc")

    # set modified
    mrc.modified_changed.reset_mock()
    mrc.name_changed.reset_mock()

    mrc.modified = False

    assert not mrc.modified
    mrc.modified_changed.emit.assert_called_once_with(False)
    assert mrc.name_changed.emit.call_count == 0

    # set same name
    mrc.modified_changed.reset_mock()
    mrc.name_changed.reset_mock()

    mrc.name = "my mrc"

    assert mrc.name == "my mrc"
    assert not mrc.modified
    assert mrc.modified_changed.emit.call_count == 0
    assert mrc.name_changed.emit.call_count == 0

    # set url
    mrc.url_changed = mock.MagicMock()

    mrc.url = "another_url"
    assert mrc.modified
    mrc.url_changed.emit.assert_called_once_with("another_url")

def test_mrc_device():
    mrc = cm.MRC("the_url")
    device = cm.Device(0, 0, 1)

    # add device
    mrc.add_device(device)
    assert mrc.modified
    assert device.mrc == mrc
    assert not device.modified

    # modify device should propagate to mrc
    mrc.modified = False
    device.name = "my device"
    assert mrc.modified
    assert device.modified

    # modify should propagate to device
    mrc.modified = False
    assert not mrc.modified
    assert not device.modified

    # remove device
    mrc.device_removed = mock.MagicMock()

    mrc.remove_device(device)

    assert mrc.modified
    assert not device.modified
    mrc.device_removed.emit.assert_called_once_with(device)

    mrc.modified = False
    device.name = "your device"
    assert not mrc.modified
    assert device.modified

def test_device():
    d = cm.Device(0, 0, 1)

    assert not d.modified
    assert d.name == str()

    d.bus_changed = mock.MagicMock()
    d.address_changed = mock.MagicMock()
    d.idc_changed = mock.MagicMock()
    d.mrc_changed = mock.MagicMock()
    d.parameter_changed = mock.MagicMock()

    d.bus = 1
    assert d.modified
    assert d.bus == 1
    d.bus_changed.emit.assert_called_once_with(1)

    d.modified = False
    d.address = 1
    assert d.modified
    assert d.address == 1
    d.address_changed.emit.assert_called_once_with(1)

    d.modified = False
    d.idc = 42
    assert d.modified
    assert d.idc == 42
    d.idc_changed.emit.assert_called_once_with(42)

    d.modified = False
    d.set_cached_parameter(0, 13)
    assert d.modified
    assert d.get_cached_parameter(0) == 13
    d.parameter_changed.emit.assert_called_once_with(0, 13)

    d.modified = False
    d.parameter_changed.reset_mock()

    d.set_cached_parameter(1, 14)
    assert d.modified
    assert d.get_cached_parameter(1) == 14
    d.parameter_changed.emit.assert_called_once_with(1, 14)

    f = d.read_parameter(0)
    assert f.result().value == 13

    f = d.read_parameter(10)
    assert_raises(KeyError, f.result)
