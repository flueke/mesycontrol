#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from xml.dom import minidom
from xml.etree import ElementTree
from xml.etree.ElementTree import TreeBuilder
from config import Config, MRCConnectionConfig, DeviceConfig, ParameterConfig
from device_description import DeviceDescription, ParameterDescription

class InvalidArgument(RuntimeError):
    pass

def parse_file(filename):
    return parse_etree(ElementTree.parse(filename))

def parse_string(xml_str):
    return parse_etree(ElementTree.ElementTree(ElementTree.fromstring(xml_str)))

def parse_etree(et):
    root = et.getroot()
    if root.tag != 'mesycontrol':
        raise InvalidArgument("invalid root tag '%s', expected 'mesycontrol'" % root.tag)
    return parse_etree_element(root)

def parse_etree_element(element):
    config = Config()

    for desc_node in element.iter('device_description'):
        config.device_descriptions.append(parse_device_description(desc_node))

    for config_node in element.iter('device_config'):
        config.device_configs.append(parse_device_config(config_node))

    for connection_node in element.iter('mrc_connection'):
        config.mrc_connections.append(parse_mrc_connection_config(connection_node))

    return config

def parse_device_description(desc_node):
    device_desc = DeviceDescription(desc_node.find('idc').text)

    n = desc_node.find('name')
    if n is not None:
        device_desc.name = n.text

    for param_node in desc_node.iter('parameter'):
        param_desc         = ParameterDescription(param_node.find('address').text)

        n = param_node.find('name')
        param_desc.name    = n.text if n is not None else None

        n = param_node.find('poll')
        param_desc.poll = True if n is not None and int(n.text) else False

        n = param_node.find('read_only')
        param_desc.read_only = True if n is not None and int(n.text) else False

        n = param_node.find('critical')
        param_desc.critical = True if n is not None and int(n.text) else False

        n = param_node.find('safe_value')
        param_desc.safe_value = int(n.text) if n is not None else 0

        n = param_node.find('do_not_store')
        param_desc.do_not_store = True if n is not None and int(n.text) else False

        device_desc.add_parameter(param_desc)

    return device_desc

def parse_device_config(config_node):
    device_config = DeviceConfig(config_node.find('device_idc').text)

    n = config_node.find('name')
    if n is not None:
        device_config.name = n.text

    n = config_node.find('connection_name')
    if n is not None:
        device_config.connection_name = n.text

    n = config_node.find('bus_number')
    if n is not None:
        device_config.bus_number = n.text

    n = config_node.find('device_address')
    if n is not None:
        device_config.device_address = n.text

    for param_node in config_node.iter('parameter_config'):
        param_config = ParameterConfig(param_node.find('address').text)

        n = param_node.find('value')
        if n is not None:
            param_config.value = n.text

        n = param_node.find('alias')
        if n is not None:
            param_config.alias = n.text

        device_config.add_parameter(param_config)

    return device_config

def parse_mrc_connection_config(connection_node):
    connection_config = MRCConnectionConfig()

    n = connection_node.find('name')
    if n is not None:
        connection_config.name = n.text

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

def to_etree(config):
    tb = TreeBuilder()
    tb.start("mesycontrol", {})

    for obj in config.mrc_connections:
        _mrc_connection_config_to_etree(obj, tb)

    for obj in config.device_configs:
        _device_config_to_etree(obj, tb)

    for obj in config.device_descriptions:
        _device_description_to_etree(obj, tb)

    tb.end("mesycontrol")

    return ElementTree.ElementTree(tb.close())

def write_file(cfg, f):
    xml = ElementTree.tostring(to_etree(cfg).getroot())
    xml = minidom.parseString(xml).toprettyxml(indent='  ')
    f.write(xml)

def _mrc_connection_config_to_etree(cfg, tb):
    tb.start('mrc_connection', {})
    _add_tag(tb, 'name', cfg.name)

    if cfg.is_mesycontrol_connection():
        _add_tag(tb, 'mesycontrol_host', cfg.mesycontrol_host)
        _add_tag(tb, 'mesycontrol_port', cfg.mesycontrol_port)

    elif cfg.is_tcp_connection():
        _add_tag(tb, 'tcp_host', cfg.tcp_host)
        _add_tag(tb, 'tcp_port', cfg.tcp_port)

    elif cfg.is_serial_connection():
        _add_tag(tb, 'serial_device', cfg.serial_device)
        _add_tag(tb, 'serial_baud_rate', cfg.serial_baud_rate)

    tb.end('mrc_connection')

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

def _device_config_to_etree(cfg, tb):
    tb.start('device_config', {})

    _add_tag(tb, 'device_idc', cfg.device_idc)

    if cfg.name is not None:
        _add_tag(tb, 'name', cfg.name)

    if cfg.connection_name is not None:
        _add_tag(tb, 'connection_name', cfg.connection_name)

    if cfg.bus_number is not None:
        _add_tag(tb, 'bus_number', cfg.bus_number)

    if cfg.device_address is not None:
        _add_tag(tb, 'device_address', cfg.device_address)

    for p in cfg.get_parameters():
        if p.value is not None or p.alias:
            tb.start("parameter_config", {})

            _add_tag(tb, "address", str(p.address))

            if p.value is not None:
                _add_tag(tb, "value", str(p.value))

            if p.alias:
                _add_tag(tb, "alias", str(p.alias))

            tb.end("parameter_config")

    tb.end("device_config")

def _add_tag(tb, tag, text, attrs = {}):
    tb.start(tag, {})
    tb.data(str(text))
    tb.end(tag)
