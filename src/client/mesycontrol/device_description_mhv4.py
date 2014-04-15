#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from device_description import DeviceDescription

description_dict = {
        'name': 'MHV4',
        'idc': 17,
        'parameters': [
            { 'address': 0,   'name': 'channel1_voltage_write' },
            { 'address': 1,   'name': 'channel2_voltage_write' },
            { 'address': 2,   'name': 'channel3_voltage_write' },
            { 'address': 3,   'name': 'channel4_voltage_write' },

            { 'address': 32,  'name': 'channel1_voltage_read', 'poll': True, 'read_only': True },
            { 'address': 33,  'name': 'channel2_voltage_read', 'poll': True, 'read_only': True },
            { 'address': 34,  'name': 'channel3_voltage_read', 'poll': True, 'read_only': True },
            { 'address': 35,  'name': 'channel4_voltage_read', 'poll': True, 'read_only': True },

            # Mark channel enable setting as critical. 
            { 'address': 4,   'name': 'channel1_enable_write', 'critical': True },
            { 'address': 5,   'name': 'channel2_enable_write', 'critical': True },
            { 'address': 6,   'name': 'channel3_enable_write', 'critical': True },
            { 'address': 7,   'name': 'channel4_enable_write', 'critical': True },

            { 'address': 36,  'name': 'channel1_enable_read', 'read_only': True },
            { 'address': 37,  'name': 'channel2_enable_read', 'read_only': True },
            { 'address': 38,  'name': 'channel3_enable_read', 'read_only': True },
            { 'address': 39,  'name': 'channel4_enable_read', 'read_only': True },
            ]
        }

instance = DeviceDescription.fromDict(description_dict)

def get_device_description():
    return instance

if __name__ == "__main__":
    from device_config_xml import DeviceConfigXML
    from xml.dom import minidom
    from xml.etree import ElementTree

    device_description = get_device_description()
    xml_string = ElementTree.tostring(DeviceConfigXML.to_etree([device_description]).getroot())
    xml_string = minidom.parseString(xml_string).toprettyxml(indent='  ')

    print "DeviceDescription XML for idc=%d, name=%s:" % (device_description.idc, device_description.name)
    print
    print xml_string
    print
    print "Parsing generated XML...",

    device_descriptions, device_configs = DeviceConfigXML.parse_string(xml_string)

    assert len(device_descriptions) == 1
    assert len(device_configs) == 0
    assert device_descriptions[0] == device_description

    print "OK!"
