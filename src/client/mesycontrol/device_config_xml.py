#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from xml.etree import ElementTree
from xml.etree.ElementTree import TreeBuilder
from device_config import DeviceConfig
from device_description import DeviceDescription, ParameterDescription

class InvalidArgument(RuntimeError):
    pass

class DeviceConfigXML(object):
    @staticmethod
    def parse_file(filename):
        return DeviceConfigXML.parse_etree(ElementTree.ElementTree(ElementTree.parse(filename)))

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
            device_desc      = DeviceDescription()
            device_desc.idc  = int(desc_node.find('idc').text)
            device_desc.name = desc_node.find('name').text

            for param_node in desc_node.iter('parameter'):
                param_desc         = ParameterDescription()
                param_desc.address = int(param_node.find('address').text)
                param_desc.name    = param_node.find('name').text

                n = param_node.find('poll')
                param_desc.poll = True if n is not None and int(n.text) else False

                n = param_node.find('read_only')
                param_desc.read_only = True if n is not None and int(n.text) else False

                n = param_node.find('critical')
                param_desc.critical = True if n is not None and int(n.text) else False

                n = param_node.find('safe_value')
                param_desc.safe_value = int(n.text) if n is not None else 0

                device_desc.parameters.append(param_desc)

            device_descriptions.append(device_desc)

        device_configs = []

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
        DeviceConfigXML._add_tag(tb, "name", desc.name)

        for pd in desc.parameters:
            tb.start("parameter", {})

            DeviceConfigXML._add_tag(tb, "address", str(pd.address))
            DeviceConfigXML._add_tag(tb, "name", pd.name)

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
        descr_file = None

        if isinstance(cfg.device_description, DeviceDescription):
            descr_name = cfg.device_description.name
        elif isinstance(cfg.device_description, str):
            descr_name = cfg.device_description
        elif isinstance(cfg.device_description_file, str):
            descr_file = cfg.device_description_file

        tb.start("device_config", {})

        if descr_name:
            DeviceConfigXML._add_tag(tb, "device_description_name", descr_name)
        elif descr_file:
            DeviceConfigXML._add_tag(tb, "device_description_file", descr_file)

        if cfg.alias:
            DeviceConfigXML._add_tag(tb, "alias", cfg.alias)

        if cfg.mrc_address:
            DeviceConfigXML._add_tag(tb, "mrc_address", cfg.mrc_address)
        elif cfg.mesycontrol_server:
            DeviceConfigXML._add_tag(tb, "mesycontrol_server", cfg.mesycontrol_server)

        if not cfg.bus_number is None and not cfg.device_number is None:
            DeviceConfigXML._add_tag(tb, "bus_number", str(cfg.bus_number))
            DeviceConfigXML._add_tag(tb, "device_number", str(cfg.device_number))

        for p in cfg.parameters:
            tb.start("parameter", {})

            DeviceConfigXML._add_tag(tb, "address", str(p.address))
            DeviceConfigXML._add_tag(tb, "value", str(p.value))

            if p.alias:
                DeviceConfigXML._add_tag(tb, "alias", p.alias)

            tb.end("parameter")

        tb.end("device_config")

    @staticmethod
    def _add_tag(tb, tag, text, attrs = {}):
        tb.start(tag, {})
        tb.data(text)
        tb.end(tag)
