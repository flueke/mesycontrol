#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from xml.dom import minidom
from xml.etree import ElementTree
from xml.etree.ElementTree import TreeBuilder

import config

class CommentTreeBuilder(TreeBuilder):
    def comment(self, data):
        self.start(ElementTree.Comment, {})
        self.data(data)
        self.end(ElementTree.Comment)

class InvalidArgument(RuntimeError):
    pass

def parse_file(filename):
    ret = parse_etree(ElementTree.parse(filename))
    ret.filename = filename
    ret.modified = False
    return ret

def parse_string(xml_str):
    return parse_etree(ElementTree.ElementTree(ElementTree.fromstring(xml_str)))

def parse_etree(et):
    root = et.getroot()
    if root.tag != 'mesycontrol':
        raise InvalidArgument("invalid root tag '%s', expected 'mesycontrol'" % root.tag)
    return parse_setup(root)

def parse_setup(element):
    ret = config.Setup()

    n = element.find('name')
    if n is not None:
        ret.name = n.text

    n = element.find('description')
    if n is not None:
        ret.description = n.text

    for config_node in element.findall('device_config'):
        ret.add_device_config(parse_device_config(config_node))

    for mrc_node in element.findall('mrc_config'):
        ret.add_mrc_config(parse_mrc_config(mrc_node))

    ret.modified = False

    return ret

def setup_to_etree(setup, context):
    tb = CommentTreeBuilder()
    tb.start("mesycontrol", {})

    _add_tag(tb, 'name', setup.name)
    _add_tag(tb, 'description', setup.description)

    for dev_cfg in setup.get_device_configs():
        dev_profile = context.get_device_profile_by_idc(dev_cfg.idc)
        _device_config_to_etree(dev_cfg, dev_profile, tb)

    for mrc_cfg in setup.get_mrc_configs():
        _mrc_config_to_etree(mrc_cfg, tb, context)

    tb.end("mesycontrol")

    return ElementTree.ElementTree(tb.close())

def device_config_to_etree(device_config, context):
    tb = CommentTreeBuilder()
    dev_profile = context.get_device_profile_by_idc(device_config.idc)
    _device_config_to_etree(device_config, dev_profile, tb)
    return ElementTree.ElementTree(tb.close())

def mrc_config_to_etree(mrc_config, context):
    tb = CommentTreeBuilder()
    _mrc_config_to_etree(mrc_config, tb, context)
    return ElementTree.ElementTree(tb.close())

def write_device_config_to_file(device_config, f, context):
    tb = CommentTreeBuilder()
    tb.start("mesycontrol", {})
    dev_profile = context.get_device_profile_by_idc(device_config.idc)
    _device_config_to_etree(device_config, dev_profile, tb)
    tb.end("mesycontrol")

    tree = ElementTree.ElementTree(tb.close())
    f.write(xml_tree_to_string(tree))

def parse_device_config(config_node):
    device_config = config.DeviceConfig()

    n = config_node.find('idc')
    if n is not None:
        device_config.idc = n.text

    n = config_node.find('name')
    if n is not None:
        device_config.name = n.text

    n = config_node.find('description')
    if n is not None:
        device_config.description = n.text

    n = config_node.find('bus')
    if n is not None:
        device_config.bus = n.text

    n = config_node.find('address')
    if n is not None:
        device_config.address = n.text

    n = config_node.find('rc')
    if n is not None:
        int_val = int(n.text)
        device_config.rc = int_val != 0

    for param_node in config_node.iter('parameter_config'):
        attribs = dict(param_node.attrib)
        if 'name' in attribs:
            del attribs['name']
        param_config = config.ParameterConfig(**attribs)
        device_config.add_parameter_config(param_config)

    return device_config

def _device_config_to_etree(cfg, profile, tb):
    tb.start('device_config', {})

    _add_tag(tb, 'idc', cfg.idc)

    if cfg.name is not None:
        _add_tag(tb, 'name', cfg.name)

    if cfg.description is not None:
        _add_tag(tb, 'description', cfg.description)

    if cfg.bus is not None:
        _add_tag(tb, 'bus', cfg.bus)

    if cfg.address is not None:
        _add_tag(tb, 'address', cfg.address)

    if cfg.rc is not None:
        _add_tag(tb, 'rc', 1 if cfg.rc else 0)

    for p in cfg.get_parameters():
        if p.value is None and p.alias is None:
            continue

        attrs = dict(address=str(p.address))

        if p.value is not None:
            attrs['value'] = str(p.value)

        if p.alias is not None:
            attrs['alias'] = str(p.alias)

        param_profile = profile.get_parameter_by_address(p.address)

        if param_profile is not None and param_profile.is_named():
            tb.comment(param_profile.name)

        tb.start("parameter_config", attrs)
        tb.end("parameter_config")

    tb.end("device_config")

def parse_mrc_config(config_node):
    ret = config.MRCConfig()

    n = config_node.find('name')
    if n is not None:
        ret.name = n.text

    n = config_node.find('description')
    if n is not None:
        ret.description = n.text

    n = config_node.find('connection_config')
    if n is not None:
        ret.set_connection_config(parse_connection_config(n))

    for n in config_node.iter('device_config'):
        ret.add_device_config(parse_device_config(n))

    return ret

def _mrc_config_to_etree(cfg, tb, context):
    tb.start('mrc_config', {})

    if cfg.name is not None:
        _add_tag(tb, 'name', cfg.name)

    if cfg.description is not None:
        _add_tag(tb, 'description', cfg.description)

    if cfg.get_connection_config() is not None:
        _connection_config_to_etree(cfg.get_connection_config(), tb)

    for dev_cfg in cfg.get_device_configs():
        dev_profile = context.get_device_profile_by_idc(dev_cfg.idc)
        _device_config_to_etree(dev_cfg, dev_profile, tb)

    tb.end('mrc_config')

def parse_connection_config(connection_node):
    connection_config = config.MRCConnectionConfig()

    # mesycontrol
    n = connection_node.find('mesycontrol_host')
    if n is not None:
        connection_config.mesycontrol_host = n.text

    n = connection_node.find('mesycontrol_port')
    if n is not None:
        connection_config.mesycontrol_port = n.text

    # serial
    n = connection_node.find('serial_device')
    if n is not None:
        connection_config.serial_device = n.text

    n = connection_node.find('serial_baud_rate')
    if n is not None:
        connection_config.serial_baud_rate = n.text

    # tcp
    n = connection_node.find('tcp_host')
    if n is not None:
        connection_config.tcp_host = n.text

    n = connection_node.find('tcp_port')
    if n is not None:
        connection_config.tcp_port = n.text

    return connection_config

def write_setup_to_file(setup, f, context):
    tree = setup_to_etree(setup, context)
    f.write(xml_tree_to_string(tree))

def xml_tree_to_string(tree):
    ugly   = ElementTree.tostring(tree.getroot())
    pretty = minidom.parseString(ugly).toprettyxml(indent='  ')
    return pretty

def _connection_config_to_etree(cfg, tb):
    tb.start('connection_config', {})

    if cfg.is_mesycontrol_connection():
        _add_tag(tb, 'mesycontrol_host', cfg.mesycontrol_host)
        _add_tag(tb, 'mesycontrol_port', cfg.mesycontrol_port)

    elif cfg.is_tcp_connection():
        _add_tag(tb, 'tcp_host', cfg.tcp_host)
        _add_tag(tb, 'tcp_port', cfg.tcp_port)

    elif cfg.is_serial_connection():
        _add_tag(tb, 'serial_device', cfg.serial_device)
        _add_tag(tb, 'serial_baud_rate', cfg.serial_baud_rate)

    tb.end('connection_config')

#def parse_device_description(desc_node):
#    device_desc = DeviceDescription(desc_node.find('idc').text)
#
#    n = desc_node.find('name')
#    if n is not None:
#        device_desc.name = n.text
#
#    for param_node in desc_node.iter('parameter'):
#        param_desc         = ParameterDescription(param_node.find('address').text)
#
#        n = param_node.find('name')
#        param_desc.name    = n.text if n is not None else None
#
#        n = param_node.find('poll')
#        param_desc.poll = True if n is not None and int(n.text) else False
#
#        n = param_node.find('read_only')
#        param_desc.read_only = True if n is not None and int(n.text) else False
#
#        n = param_node.find('critical')
#        param_desc.critical = True if n is not None and int(n.text) else False
#
#        n = param_node.find('safe_value')
#        param_desc.safe_value = int(n.text) if n is not None else 0
#
#        n = param_node.find('do_not_store')
#        param_desc.do_not_store = True if n is not None and int(n.text) else False
#
#        device_desc.add_parameter(param_desc)
#
#    return device_desc

def _device_description_to_etree(desc, tb):
    tb.start("device_description", {})

    _add_tag(tb, "idc", str(desc.idc))
    if desc.name is not None:
        _add_tag(tb, "name", str(desc.name))

    for pd in desc.parameters.values():
        tb.start("parameter", {})

        _add_tag(tb, "address", str(pd.address))

        if pd.name is not None:
            _add_tag(tb, "name", str(pd.name))

        if pd.poll:
            _add_tag(tb, "poll", "1")

        if pd.read_only:
            _add_tag(tb, "read_only", "1")

        if pd.critical:
            _add_tag(tb, "critical", "1")

        if pd.safe_value:
            _add_tag(tb, "safe_value", str(pd.safe_value))

        if pd.do_not_store:
            _add_tag(tb, "do_not_store", "1")

        tb.end("parameter")

    tb.end("device_description")

def _add_tag(tb, tag, text, attrs = {}):
    tb.start(tag, {})
    tb.data(str(text))
    tb.end(tag)
