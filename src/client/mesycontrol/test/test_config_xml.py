#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import difflib
import StringIO

from .. import config_model as cm
from .. import config_xml as cxml
from .. qt import QtCore
from xml.etree import ElementTree as ET

expected = """<?xml version="1.0" ?>
<mesycontrol version="1">
  <device_config>
    <idc>20</idc>
    <bus>1</bus>
    <address>15</address>
    <name>my test thing</name>
    <!--param 0-->
    <parameter address="0" value="0"/>
    <!--param 1-->
    <parameter address="1" value="1"/>
    <!--param 2-->
    <parameter address="2" value="4"/>
    <!--param 3-->
    <parameter address="3" value="9"/>
    <!--param 4-->
    <parameter address="4" value="16"/>
    <!--param 5-->
    <parameter address="5" value="25"/>
    <!--param 6-->
    <parameter address="6" value="36"/>
    <!--param 7-->
    <parameter address="7" value="49"/>
    <!--param 8-->
    <parameter address="8" value="64"/>
    <!--param 9-->
    <parameter address="9" value="81"/>
  </device_config>
</mesycontrol>
"""

expected2 = """<?xml version="1.0" ?>
<mesycontrol version="1">
  <setup>
    <mrc_config>
      <url>/dev/ttyUSB0</url>
      <name>the_mrc</name>
      <device_config>
        <idc>1</idc>
        <bus>0</bus>
        <address>0</address>
        <name>d1</name>
        <!--idc=1, p=0-->
        <parameter address="0" value="0"/>
        <!--idc=1, p=1-->
        <parameter address="1" value="1"/>
        <!--idc=1, p=2-->
        <parameter address="2" value="4"/>
        <!--idc=1, p=3-->
        <parameter address="3" value="9"/>
        <!--idc=1, p=4-->
        <parameter address="4" value="16"/>
        <!--idc=1, p=5-->
        <parameter address="5" value="25"/>
        <!--idc=1, p=6-->
        <parameter address="6" value="36"/>
        <!--idc=1, p=7-->
        <parameter address="7" value="49"/>
        <!--idc=1, p=8-->
        <parameter address="8" value="64"/>
        <!--idc=1, p=9-->
        <parameter address="9" value="81"/>
        <parameter address="10" value="100"/>
        <parameter address="11" value="121"/>
      </device_config>
      <device_config>
        <idc>2</idc>
        <bus>1</bus>
        <address>5</address>
        <name>d2</name>
        <!--idc=2, p=0-->
        <parameter address="0" value="0"/>
        <!--idc=2, p=1-->
        <parameter address="1" value="1"/>
        <!--idc=2, p=2-->
        <parameter address="2" value="8"/>
        <!--idc=2, p=3-->
        <parameter address="3" value="27"/>
        <!--idc=2, p=4-->
        <parameter address="4" value="64"/>
        <!--idc=2, p=5-->
        <parameter address="5" value="125"/>
        <!--idc=2, p=6-->
        <parameter address="6" value="216"/>
        <!--idc=2, p=7-->
        <parameter address="7" value="343"/>
        <!--idc=2, p=8-->
        <parameter address="8" value="512"/>
        <!--idc=2, p=9-->
        <parameter address="9" value="729"/>
        <parameter address="10" value="1000"/>
        <parameter address="11" value="1331"/>
      </device_config>
    </mrc_config>
    <mrc_config>
      <url>/dev/ttyUSB1</url>
      <name>the_2nd_mrc</name>
      <device_config>
        <idc>2</idc>
        <bus>0</bus>
        <address>7</address>
        <name>d3</name>
        <!--idc=2, p=0-->
        <parameter address="0" value="0"/>
        <!--idc=2, p=1-->
        <parameter address="1" value="1"/>
        <!--idc=2, p=2-->
        <parameter address="2" value="1"/>
        <!--idc=2, p=3-->
        <parameter address="3" value="1"/>
        <!--idc=2, p=4-->
        <parameter address="4" value="2"/>
        <!--idc=2, p=5-->
        <parameter address="5" value="2"/>
        <!--idc=2, p=6-->
        <parameter address="6" value="2"/>
        <!--idc=2, p=7-->
        <parameter address="7" value="2"/>
        <!--idc=2, p=8-->
        <parameter address="8" value="2"/>
        <!--idc=2, p=9-->
        <parameter address="9" value="3"/>
        <parameter address="10" value="3"/>
        <parameter address="11" value="3"/>
      </device_config>
    </mrc_config>
  </setup>
</mesycontrol>
"""

def test_write_device_config():
    device = cm.Device(bus=1, address=15, idc=20)
    device.name = 'my test thing'
    dest   = StringIO.StringIO()
    param_names = dict()

    for i in range(10):
        device.set_parameter(i, i*i)
        param_names[i] = 'param %i' % i

    cxml.write_device_config(device, dest, param_names)

    actual = dest.getvalue()

    try:
        assert actual == expected
    except AssertionError:
        print "test_write_device_config diff:"
        for l in difflib.unified_diff(expected.splitlines(), actual.splitlines(),
                "expected", "actual"):
            print l
        raise

def test_read_device_config():
    source = StringIO.StringIO(expected)

    device = cxml.read_device_config(source)
    
    assert device.name == 'my test thing'
    assert device.idc  == 20
    assert device.bus  == 1
    assert device.address == 15

    for i in range(10):
        assert device.get_cached_parameter(i) == i*i

    assert not device.modified

def test_write_setup():
    import math

    idc_to_param_names = {1:{}, 2:{}}

    for i in range(10):
        idc_to_param_names[1][i] = 'idc=1, p=%i' % i
        idc_to_param_names[2][i] = 'idc=2, p=%i' % i

    d1 = cm.Device(bus=0, address=0, idc=1)
    d1.name = 'd1'

    d2 = cm.Device(bus=1, address=5, idc=2)
    d2.name = 'd2'

    d3 = cm.Device(bus=0, address=7, idc=2)
    d3.name = 'd3'

    for i in range(12):
        d1.set_parameter(i, i*i)
        d2.set_parameter(i, i*i*i)
        d3.set_parameter(i, math.sqrt(i))

    mrc1 = cm.MRC(url='/dev/ttyUSB0')
    mrc1.name = 'the_mrc'
    mrc1.add_device(d1)
    mrc1.add_device(d2)

    mrc2 = cm.MRC(url='/dev/ttyUSB1')
    mrc2.name = 'the_2nd_mrc'
    mrc2.add_device(d3)

    setup = cm.Setup()
    setup.add_mrc(mrc1)
    setup.add_mrc(mrc2)

    dest = StringIO.StringIO()

    cxml.write_setup(setup, dest, idc_to_param_names)

    actual = dest.getvalue()

    try:
        assert actual == expected2
    except AssertionError:
        print "test_write_device_config diff:"
        for l in difflib.unified_diff(expected2.splitlines(), actual.splitlines(),
                "expected", "actual"):
            print l
        raise

def test_read_setup():
    source = StringIO.StringIO(expected2)

    setup = cxml.read_setup(source)

    assert not setup.modified
    assert len(setup.get_mrcs()) == 2
    assert setup.get_mrc('/dev/ttyUSB0').get_device(0, 0).idc == 1
    assert setup.get_mrc('/dev/ttyUSB1').get_device(0, 7).idc == 2

def test_value2xml_string_types():
    tb = cxml.CommentTreeBuilder()

    l = [
            "Hello World!",
            u"Hello Unicode World!",
            QtCore.QString("Hello QString World!"),
            u"Hello unicode €uro World!",
            QtCore.QString.fromUtf8("Hello QString.fromUtf8 €uro World!")
            ]

    for txt in l:
        cxml.value2xml(tb, txt)
        tree = ET.ElementTree(tb.close())
        xml = cxml._xml_tree_to_string(tree)

        et = ET.fromstring(xml.encode('utf-8'))
        value = cxml.xml2value(et)

        print type(txt), type(value)

        assert txt == value
