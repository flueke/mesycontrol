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
__email__  = 'florianlueke@gmx.net'

from nose.tools import assert_raises, assert_dict_equal
from mesycontrol.util import parse_connection_url
from mesycontrol.util import URLParseError
from mesycontrol import util

def test_parse_connection_url():
    for url in ('serial:///dev/ttyUSB0@115200', '/dev/ttyUSB0@115200'):
        d = parse_connection_url(url)
        assert_dict_equal(d, dict(serial_port='/dev/ttyUSB0', baud_rate=115200))

    for url in ('serial:///dev/ttyUSB0', '/dev/ttyUSB0'):
        d = parse_connection_url(url)
        assert_dict_equal(d, dict(serial_port='/dev/ttyUSB0', baud_rate=0), 'failed for url=%s' % url)

    for url in ('serial:///dev/ttyUSB0@', '/dev/ttyUSB0@',
            'serial:///dev/ttyUSB0@foo', '/dev/ttyUSB0@foo',
            'serial://@', '@9600', 'serial://@9600', '@', 'serial://'):
        assert_raises(URLParseError, parse_connection_url, url)

    d = parse_connection_url('tcp://example.com:666')
    assert_dict_equal(d, dict(host='example.com', port=666))

    d = parse_connection_url('tcp://example.com')
    assert_dict_equal(d, dict(host='example.com', port=4001))

    d = parse_connection_url('example.com:666')
    assert_dict_equal(d, dict(host='example.com', port=666))

    for url in ('tcp://example.com:', 'example.com:', 'tcp://example.com:foo',
            'example.com:foo', 'tcp://:', ':666', 'tcp://:666', ':', 'tcp://'):
        assert_raises(URLParseError, parse_connection_url, url)

    d = parse_connection_url('mc://example.com:666')
    assert_dict_equal(d, dict(mc_host='example.com', mc_port=666))

    d = parse_connection_url('mc://example.com')
    assert_dict_equal(d, dict(mc_host='example.com', mc_port=23000))

    for url in ('mc://example.com:', 'mc://example.com:foo',
            'mc://:', 'mc://:666',
            'mc://'):
        assert_raises(URLParseError, parse_connection_url, url)

    for url in ('://', 'fooproto://foo:bar'):
        assert_raises(URLParseError, parse_connection_url, url)

def test_make_logging_source_adapter():
    class TestClass():
        pass

    test_instance = TestClass()

    log = util.make_logging_source_adapter(__name__, test_instance)
    assert log.logger.name == "%s.%s" % (__name__, test_instance.__class__.__name__)
