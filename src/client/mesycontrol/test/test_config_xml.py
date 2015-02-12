#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from .. import app_context
from .. import config
from .. import config_xml
from nose.tools import assert_raises
import xml.etree.ElementTree as ET

def test_device_config_xml():
    context = app_context.Context(__file__)

    cfg = config.DeviceConfig()
    cfg.name        = 'foobar'
    cfg.description = 'lorem ipsum'
    cfg.idc         = 1
    cfg.bus         = 0
    cfg.address     = 15
    cfg.rc          = False

    for i in range(50, 100):
        cfg.add_parameter(i, i*2, str(i*2))

    xml_tree   = config_xml.device_config_to_etree(cfg, context)

    print
    print '==============='
    print config_xml.xml_tree_to_string(xml_tree)
    print '==============='

    parsed_cfg = config_xml.parse_device_config(xml_tree.getroot())

    assert cfg.name         == parsed_cfg.name
    assert cfg.description  == parsed_cfg.description
    assert cfg.idc          == parsed_cfg.idc
    assert cfg.bus          == parsed_cfg.bus
    assert cfg.address      == parsed_cfg.address
    assert cfg.rc           == parsed_cfg.rc

    for i in range(50, 100):
        assert parsed_cfg.contains_parameter(i)
        param_cfg = parsed_cfg.get_parameter(i)
        assert param_cfg.address == i
        assert param_cfg.value   == i*2
        assert param_cfg.alias   == str(i*2)

def test_mrc_config_xml():
    context = app_context.Context(__file__)

    mrc_cfg             = config.MRCConfig()
    mrc_cfg.name        = 'foobar'
    mrc_cfg.description = 'lorem ipsum'

    connection_config                  = config.MRCConnectionConfig()
    connection_config.serial_device    = '/dev/null'
    connection_config.serial_baud_rate = 115200

    mrc_cfg.connection_config = connection_config

    for i in range(2):
        dev_cfg         = config.DeviceConfig()
        dev_cfg.name    = 'device %d' % i
        dev_cfg.idc     = 17
        dev_cfg.bus     = i
        dev_cfg.address = 7
        dev_cfg.rc      = True

        for j in range(10):
            dev_cfg.add_parameter(j, j+42)

        mrc_cfg.add_device_config(dev_cfg)

    xml_tree = config_xml.mrc_config_to_etree(mrc_cfg, context)

    print
    print '==============='
    print config_xml.xml_tree_to_string(xml_tree)
    print '==============='

    parsed_mrc_cfg = config_xml.parse_mrc_config(xml_tree.getroot())
    
    assert mrc_cfg.name == parsed_mrc_cfg.name
    assert mrc_cfg.description == parsed_mrc_cfg.description
    assert mrc_cfg.connection_config.serial_device == parsed_mrc_cfg.connection_config.serial_device
    assert mrc_cfg.connection_config.serial_baud_rate == parsed_mrc_cfg.connection_config.serial_baud_rate

    for i in range(2):
        dev_cfg = parsed_mrc_cfg.get_device_config(i, 7)
        assert dev_cfg.idc == 17
        assert dev_cfg.bus == i
        assert dev_cfg.address == 7
        assert dev_cfg.rc == True

def test_setup_config_xml():
    context = app_context.Context(__file__)

    setup = config.Setup()
    setup.name = 'foobar setup'
    setup.description = 'lorem setup'

    # single top-level DeviceConfig
    dev_cfg = config.DeviceConfig()
    dev_cfg.name        = 'foobar'
    dev_cfg.description = 'lorem ipsum'
    dev_cfg.idc         = 1
    dev_cfg.bus         = 0
    dev_cfg.address     = 15
    dev_cfg.rc          = False

    for i in range(50, 100):
        dev_cfg.add_parameter(i, i*2, str(i*2))

    setup.add_device_config(dev_cfg)

    # MRC config
    mrc_cfg             = config.MRCConfig()
    mrc_cfg.name        = 'foobar'
    mrc_cfg.description = 'lorem ipsum'

    connection_config                  = config.MRCConnectionConfig()
    connection_config.serial_device    = '/dev/null'
    connection_config.serial_baud_rate = 115200

    mrc_cfg.connection_config = connection_config

    for i in range(2):
        dev_cfg         = config.DeviceConfig()
        dev_cfg.name    = 'device %d' % i
        dev_cfg.idc     = 17
        dev_cfg.bus     = i
        dev_cfg.address = 7
        dev_cfg.rc      = True

        for j in range(10):
            dev_cfg.add_parameter(j, j+42)

        mrc_cfg.add_device_config(dev_cfg)

    setup.add_mrc_config(mrc_cfg)

    # to xml
    xml_tree = config_xml.setup_to_etree(setup, context)

    print
    print '==============='
    print config_xml.xml_tree_to_string(xml_tree)
    print '==============='

    parsed_setup = config_xml.parse_setup(xml_tree.getroot())

    assert parsed_setup.name == setup.name
    assert parsed_setup.description == setup.description
    assert len(parsed_setup.get_device_configs()) == 1
    assert parsed_setup.get_device_configs()[0].address == 15
    assert len(parsed_setup.get_mrc_configs()) == 1

    parsed_mrc_cfg = parsed_setup.get_mrc_configs()[0]

    assert 'foobar'         == parsed_mrc_cfg.name
    assert 'lorem ipsum'    == parsed_mrc_cfg.description
    assert '/dev/null'      == parsed_mrc_cfg.connection_config.serial_device
    assert 115200           == parsed_mrc_cfg.connection_config.serial_baud_rate

    for i in range(2):
        dev_cfg = mrc_cfg.get_device_config(i, 7)
        assert dev_cfg.idc == 17
        assert dev_cfg.bus == i
        assert dev_cfg.address == 7
        assert dev_cfg.rc == True

def test_value2xml_simple_types():
    tb = ET.TreeBuilder()
    tb.start("test", {})
    config_xml.value2xml(tb, 42)
    config_xml.value2xml(tb, 42.0)
    config_xml.value2xml(tb, "42.0")
    tb.end("test")
    assert ET.tostring(tb.close()) == '<test><value type="int">42</value><value type="float">42.0</value><value type="str">42.0</value></test>'

def test_value2xml_list():
    tb = ET.TreeBuilder()
    tb.start("test", {})
    config_xml.value2xml(tb, [1, '2', 3.0])
    tb.end("test")
    assert ET.tostring(tb.close()) == '<test><value type="list"><value type="int">1</value><value type="str">2</value><value type="float">3.0</value></value></test>'

def test_value2xml_dict():
    tb = ET.TreeBuilder()
    tb.start("test", {})
    config_xml.value2xml(tb, {'key1': 3.14, 'key2': "foobar", 'key3': 0})
    tb.end("test")
    assert ET.tostring(tb.close()) == '<test><value type="dict"><key name="key1"><value type="float">3.14</value></key><key name="key2"><value type="str">foobar</value></key><key name="key3"><value type="int">0</value></key></value></test>'

def test_value2xml_nested():
    tb = ET.TreeBuilder()
    tb.start("test", {})
    config_xml.value2xml(tb,
            ['item1', {'i2k1': 'foo', 'i2k2': 0x42, 'i2k3': ['holy', 'moly']}, 'item3'])
    tb.end("test")
    assert ET.tostring(tb.close()) == '<test><value type="list"><value type="str">item1</value><value type="dict"><key name="i2k1"><value type="str">foo</value></key><key name="i2k2"><value type="int">66</value></key><key name="i2k3"><value type="list"><value type="str">holy</value><value type="str">moly</value></value></key></value><value type="str">item3</value></value></test>'

def test_value2xml_type_error():
    class MyClass(object):
        pass

    tb = ET.TreeBuilder()
    tb.start("test", {})
    assert_raises(TypeError, config_xml.value2xml, tb, MyClass())
    tb.end("test")

def test_xml2value():
    def do_test(value):
        tb = ET.TreeBuilder()
        config_xml.value2xml(tb, value)
        xml_value = config_xml.xml2value(tb.close())
        assert value == xml_value

    do_test(42)
    do_test(42.0)
    do_test("42.0")
    do_test([1, 2, 3])
    do_test({'key1': 3.14, 'key2': "foobar", 'key3': 0})
    do_test(['item1', {'i2k1': 'foo', 'i2k2': 0x42, 'i2k3': ['holy', 'moly']}, 'item3'])
