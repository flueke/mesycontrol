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

"""Reading and writing mesycontrol config files."""

# Right now setups with the following structure are supported:
#<setup>
#   description
#   list of mrc configs
#       list of device configs
#</setup>

# MRC config:
#<mrc_config>
#   name, url
#   list of device configs
#</mrc_config>

# Device config
#<device_config>
#   device attributes here (name, bus, address, idc)
#   list of parameter configs
#   list of extensions
# </device_config>

# Root tag
#<mesycontrol version=1>
#</mesycontrol>

# Currently XML files may contain either a Setup or a single Device config.

# TODO: implement ability to add device profiles to device configs (later)

from mesycontrol.qt import QtCore

from xml.dom import minidom
from xml.etree.ElementTree import TreeBuilder
from xml.etree import ElementTree as ET

import mesycontrol.config_model as cm

version = 1

def read_setup(source):
    """Load a Setup from the given source.
    Source may be a filename or a file like object."""
    et   = ET.parse(source)
    root = et.getroot()

    if root.tag != 'mesycontrol':
        raise ValueError("invalid root tag '%s', expected 'mesycontrol'" % root.tag)

    setup_node = root.find('setup')

    if setup_node is None:
        raise ValueError("No Setup found.")

    ret = _setup_from_node(setup_node)

    if isinstance(source, (str, unicode, QtCore.QString)):
        ret.filename = source

    ret.modified = False

    return ret

def write_setup(setup, dest, idc_to_parameter_names=dict()):
    """Write the given setup to the given destination.
    Dest may be a filename or a file like object opened for writing.
    idc_to_parameter_names should map device_idc to a dictionary of
    param_address -> param_name.
    """
    tb = CommentTreeBuilder()
    tb.start('mesycontrol', {'version': str(version)})
    _build_setup_tree(setup, idc_to_parameter_names, tb)
    tb.end('mesycontrol')
    tree = ET.ElementTree(tb.close())
    data = _xml_tree_to_string(tree)

    try:
        dest.write(data.encode('utf-8'))
    except AttributeError:
        with open(dest, 'w') as fp:
            fp.write(data.encode('utf-8'))

def read_device_config(source):
    et   = ET.parse(source)
    root = et.getroot()

    if root.tag != 'mesycontrol':
        raise ValueError("invalid root tag '%s', expected 'mesycontrol'" % root.tag)

    node = root.find('device_config')

    if node is None:
        raise ValueError("No Device config found.")

    return _device_config_from_node(node)

def write_device_config(device_config, dest, parameter_names=dict()):
    """Write the given device config to destination.
    The optional parameter_names should map parameter_address to
    parameter_name. These names will be added as comments in the resulting XML.
    """
    tb = CommentTreeBuilder()
    tb.start('mesycontrol', {'version': str(version)})
    _build_device_tree(device_config, parameter_names, tb)
    tb.end('mesycontrol')
    tree = ET.ElementTree(tb.close())
    data = _xml_tree_to_string(tree)

    try:
        dest.write(data.encode('utf-8'))
    except AttributeError:
        with open(dest, 'w') as fp:
            fp.write(data.encode('utf-8'))

class CommentTreeBuilder(TreeBuilder):
    def comment(self, data):
        self.start(ET.Comment, {})
        self.data(data)
        self.end(ET.Comment)

def _add_attribute_tags(tb, obj, attributes):
    for attr in attributes:
        value = getattr(obj, attr, None)
        if value is not None:
            _add_tag(tb, attr, value)

def _build_device_tree(cfg, parameter_names, tb):
    tb.start('device_config', {})

    attrs = ['idc', 'bus', 'address', 'name', 'description']

    _add_attribute_tags(tb, cfg, attrs)

    for address, value in sorted(cfg.get_cached_memory().iteritems()):
        if address in parameter_names:
            tb.comment(parameter_names[address])

        _add_tag(tb=tb, tag='parameter', attrs=dict(address=str(address), value=str(value)))

    for name, value in cfg.get_extensions().iteritems():
        tb.start("extension", {'name': name})
        value2xml(tb, value)
        tb.end("extension")

    tb.end("device_config")

def _device_config_from_node(config_node):
    attrs = ['idc', 'bus', 'address', 'name', 'description']
    ret   = cm.Device()

    for attr in attrs:
        n = config_node.find(attr)
        if n is not None:
            setattr(ret, attr, n.text)

    for param_node in config_node.iter('parameter'):
        attrs = param_node.attrib
        ret.set_cached_parameter(int(attrs['address']), int(attrs['value']))

    for ext_node in config_node.iter('extension'):
        name  = ext_node.attrib['name']
        value = xml2value(ext_node.find('value'))
        ret.set_extension(name, value)

    ret.modified = False

    return ret

def _build_mrc_tree(mrc_config, idc_to_parameter_names, tb):

    attrs = ['url', 'name', 'autoconnect']

    tb.start('mrc_config', {})
    _add_attribute_tags(tb, mrc_config, attrs)

    for device in mrc_config.get_devices():
        _build_device_tree(device, idc_to_parameter_names.get(device.idc, dict()), tb)

    tb.end('mrc_config')

def _mrc_config_from_node(mrc_node):
    attrs = ['url', 'name', 'autoconnect']
    ret = cm.MRC()

    for attr in attrs:
        n = mrc_node.find(attr)
        if n is not None:
            try:
                prop_t = getattr(cm.MRC, attr).type
            except AttributeError:
                prop_t = None


            if prop_t is bool:
                prop_v = n.text.lower() in ['true', 'y', 'yes', 'on', '1']
            else:
                prop_v = n.text

            setattr(ret, attr, prop_v)

    for device_node in mrc_node.findall('device_config'):
        ret.add_device(_device_config_from_node(device_node))

    return ret

def _setup_from_node(setup_node):
    attrs = ['autoconnect']
    ret = cm.Setup()

    for attr in attrs:
        n = setup_node.find(attr)
        if n is not None:
            setattr(ret, attr, n.text)

    for mrc_node in setup_node.findall('mrc_config'):
        ret.add_mrc(_mrc_config_from_node(mrc_node))

    return ret

def _build_setup_tree(setup, idc_to_parameter_names, tb):
    attrs = ['autoconnect']

    tb.start('setup', {})
    _add_attribute_tags(tb, setup, attrs)

    for mrc in setup.get_mrcs():
        _build_mrc_tree(mrc, idc_to_parameter_names, tb)

    tb.end('setup')

def _add_tag(tb, tag, value=None, attrs = {}):
    tb.start(tag, attrs)

    if value is not None:
        tb.data(unicode(value))

    tb.end(tag)

def _xml_tree_to_string(tree):
    ugly   = ET.tostring(tree.getroot())
    pretty = minidom.parseString(ugly).toprettyxml(indent='  ')
    return pretty

def value2xml(tb, value):
    if isinstance(value, basestring):
        _add_tag(tb, "value", value, {'type': 'str'})
    elif isinstance(value, QtCore.QString):
        value = unicode(value)
        _add_tag(tb, "value", value, {'type': 'str'})
    elif isinstance(value, int):
        _add_tag(tb, "value", value, {'type': 'int'})
    elif isinstance(value, float):
        _add_tag(tb, "value", value, {'type': 'float'})
    elif isinstance(value, list):
        list2xml(tb, value)
    elif isinstance(value, dict):
        dict2xml(tb, value)
    elif isinstance(value, tuple):
        list2xml(tb, value)
    else:
        raise TypeError("value2xml: unhandled value type '%s'" % type(value).__name__)
    return tb

def list2xml(tb, l):
    tb.start("value", {'type': 'list'})
    for value in l:
        value2xml(tb, value)
    tb.end("value")
    return tb

def dict2xml(tb, d):
    tb.start("value", {'type': 'dict'})
    for k in sorted(d.keys()):
        v = d[k]
        tb.start("key", {'name': k})
        value2xml(tb, v)
        tb.end("key")
    tb.end("value")
    return tb

def xml2value(node):
    t = node.attrib['type']
    if t == 'str':
        return node.text
    elif t == 'int':
        return int(node.text)
    elif t == 'float':
        return float(node.text)
    elif t == 'list':
        return xml2list(node)
    elif t == 'dict':
        return xml2dict(node)
    else:
        raise TypeError("xml2value: unhandled value type '%s'" % t)

def xml2list(node):
    ret = list()
    for n in node.iterfind('value'):
        ret.append(xml2value(n))
    return ret

def xml2dict(node):
    ret = dict()
    for n in node.iterfind('key'):
        k = n.attrib['name']
        v = xml2value(n.find('value'))
        ret[k] = v
    return ret
