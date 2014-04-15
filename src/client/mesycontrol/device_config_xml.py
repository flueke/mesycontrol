#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from xml.etree import ElementTree
from xml.etree.ElementTree import TreeBuilder
from device_config import DeviceConfig, ParameterConfig
from device_description import DeviceDescription, ParameterDescription

class InvalidArgument(RuntimeError):
    pass

class DeviceConfigXML(object):
    @staticmethod
    def parse_file(filename):
        return DeviceConfigXML.parse_etree(ElementTree.parse(filename))

    @staticmethod
    def parse_string(xml_str):
        return DeviceConfigXML.parse_etree(ElementTree.ElementTree(ElementTree.fromstring(xml_str)))

    @staticmethod
    def parse_etree(et):
        root = et.getroot()
        if root.tag != 'mesycontrol':
            raise InvalidArgument("invalid root tag '%s', expected 'mesycontrol'" % root.tag)
        return DeviceConfigXML.parse_etree_element(root)

    @staticmethod
    def parse_etree_element(element):
        device_descriptions = []

        for desc_node in element.iter('device_description'):
            device_desc      = DeviceDescription(int(desc_node.find('idc').text))
            n = desc_node.find('name')
            device_desc.name = n.text if n is not None else None

            for param_node in desc_node.iter('parameter'):
                param_desc         = ParameterDescription(int(param_node.find('address').text))

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

                device_desc.add_parameter(param_desc)

            device_descriptions.append(device_desc)

        device_configs = []

        for config_node in element.iter('device_config'):
            device_config = DeviceConfig()

            n = config_node.find('device_description_name')
            device_config.device_description = n.text if n is not None else None

            n = config_node.find('alias')
            device_config.alias = n.text if n is not None else None

            n = config_node.find('mrc_address')
            device_config.mrc_address = n.text if n is not None else None

            n = config_node.find('mesycontrol_server')
            device_config.mesycontrol_server = n.text if n is not None else None

            n = config_node.find('bus_number')
            device_config.bus_number = n.text if n is not None else None

            n = config_node.find('device_number')
            device_config.device_number = n.text if n is not None else None

            for param_node in config_node.iter('parameter'):
                n = param_node.find('value')
                param = ParameterConfig(address=param_node.find('address').text,
                        value=int(n.text) if n is not None else None)

                n = param_node.find('alias')
                param.alias = n.text if n is not None else None

                device_config.add_parameter(param)

            device_configs.append(device_config)

        return (device_descriptions, device_configs)

    @staticmethod
    def to_etree(obj_list):
        device_descriptions = []
        device_configs = []

        for obj in obj_list:
            if isinstance(obj, DeviceDescription):
                device_descriptions.append(obj)
            elif isinstance(obj, DeviceConfig):
                device_configs.append(obj)
            else:
                raise InvalidArgument("Unexpected object type in list: %s" % type(obj))

        tb = TreeBuilder()
        tb.start("mesycontrol", {})

        for obj in device_descriptions:
            DeviceConfigXML._device_description_to_etree(obj, tb)

        for obj in device_configs:
            DeviceConfigXML._device_config_to_etree(obj, tb)

        tb.end("mesycontrol")

        return ElementTree.ElementTree(tb.close())

    @staticmethod
    def _device_description_to_etree(desc, tb):
        tb.start("device_description", {})

        DeviceConfigXML._add_tag(tb, "idc", str(desc.idc))
        if desc.name is not None:
            DeviceConfigXML._add_tag(tb, "name", str(desc.name))

        for pd in desc.parameters.values():
            tb.start("parameter", {})

            DeviceConfigXML._add_tag(tb, "address", str(pd.address))

            if pd.name is not None:
                DeviceConfigXML._add_tag(tb, "name", str(pd.name))

            if pd.poll:
                DeviceConfigXML._add_tag(tb, "poll", "1")

            if pd.read_only:
                DeviceConfigXML._add_tag(tb, "read_only", "1")

            if pd.critical:
                DeviceConfigXML._add_tag(tb, "critical", "1")

            if pd.safe_value:
                DeviceConfigXML._add_tag(tb, "safe_value", str(pd.safe_value))

            tb.end("parameter")

        tb.end("device_description")

    @staticmethod
    def _device_config_to_etree(cfg, tb):
        descr_name = None

        if isinstance(cfg.device_description, DeviceDescription):
            descr_name = cfg.device_description.name
        elif isinstance(cfg.device_description, str):
            descr_name = cfg.device_description

        tb.start("device_config", {})

        if descr_name:
            DeviceConfigXML._add_tag(tb, "device_description_name", str(descr_name))

        if cfg.alias:
            DeviceConfigXML._add_tag(tb, "alias", str(cfg.alias))

        if cfg.mrc_address:
            DeviceConfigXML._add_tag(tb, "mrc_address", str(cfg.mrc_address))
        elif cfg.mesycontrol_server:
            DeviceConfigXML._add_tag(tb, "mesycontrol_server", str(cfg.mesycontrol_server))

        if not cfg.bus_number is None and not cfg.device_number is None:
            DeviceConfigXML._add_tag(tb, "bus_number", str(cfg.bus_number))
            DeviceConfigXML._add_tag(tb, "device_number", str(cfg.device_number))

        for p in cfg.get_parameters():
            tb.start("parameter", {})

            DeviceConfigXML._add_tag(tb, "address", str(p.address))
            if p.value is not None:
                DeviceConfigXML._add_tag(tb, "value", str(p.value))

            if p.alias:
                DeviceConfigXML._add_tag(tb, "alias", str(p.alias))

            tb.end("parameter")

        tb.end("device_config")

    @staticmethod
    def _add_tag(tb, tag, text, attrs = {}):
        tb.start(tag, {})
        tb.data(text)
        tb.end(tag)
