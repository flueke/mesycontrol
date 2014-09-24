#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from device_description import DeviceDescription

description_dict = {
        'name': 'MHV-4',
        'idc': 17,
        'parameters': [
            # Voltage
            { 'address': 0,   'name': 'channel1_voltage_write', 'range': (0, 4000), 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 1,   'name': 'channel2_voltage_write', 'range': (0, 4000), 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 2,   'name': 'channel3_voltage_write', 'range': (0, 4000), 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 3,   'name': 'channel4_voltage_write', 'range': (0, 4000), 'unit': {'label': 'V', 'factor': 10.0 } },

            { 'address': 32,  'name': 'channel1_voltage_read', 'read_only': True, 'poll': True, 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 33,  'name': 'channel2_voltage_read', 'read_only': True, 'poll': True, 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 34,  'name': 'channel3_voltage_read', 'read_only': True, 'poll': True, 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 35,  'name': 'channel4_voltage_read', 'read_only': True, 'poll': True, 'unit': {'label': 'V', 'factor': 10.0 } },

            # Enable. Mark channel enable setting as critical. 
            { 'address': 4,   'name': 'channel1_enable_write', 'critical': True },
            { 'address': 5,   'name': 'channel2_enable_write', 'critical': True },
            { 'address': 6,   'name': 'channel3_enable_write', 'critical': True },
            { 'address': 7,   'name': 'channel4_enable_write', 'critical': True },

            { 'address': 36,  'name': 'channel1_enable_read', 'read_only': True },
            { 'address': 37,  'name': 'channel2_enable_read', 'read_only': True },
            { 'address': 38,  'name': 'channel3_enable_read', 'read_only': True },
            { 'address': 39,  'name': 'channel4_enable_read', 'read_only': True },

            # Current warning limits
            { 'address':  8,  'name': 'channel1_current_limit_write', 'unit': {'label': 'µA', 'factor': 100.0} },
            { 'address':  9,  'name': 'channel2_current_limit_write', 'unit': {'label': 'µA', 'factor': 100.0} },
            { 'address': 10,  'name': 'channel3_current_limit_write', 'unit': {'label': 'µA', 'factor': 100.0} },
            { 'address': 11,  'name': 'channel4_current_limit_write', 'unit': {'label': 'µA', 'factor': 100.0} },

            { 'address': 40,  'name': 'channel1_current_limit_read', 'read_only': True, 'unit': {'label': 'µA', 'factor': 100.0} },
            { 'address': 41,  'name': 'channel2_current_limit_read', 'read_only': True, 'unit': {'label': 'µA', 'factor': 100.0} },
            { 'address': 42,  'name': 'channel3_current_limit_read', 'read_only': True, 'unit': {'label': 'µA', 'factor': 100.0} },
            { 'address': 43,  'name': 'channel4_current_limit_read', 'read_only': True, 'unit': {'label': 'µA', 'factor': 100.0} },

            # Voltage range
            { 'address': 13,  'name': 'voltage_range_write' },
            { 'address': 45,  'name': 'voltage_range_read', 'read_only': True },

            # Polarity
            { 'address': 46,  'name': 'channel1_polarity_read', 'read_only': True },
            { 'address': 47,  'name': 'channel2_polarity_read', 'read_only': True },
            { 'address': 48,  'name': 'channel3_polarity_read', 'read_only': True },
            { 'address': 49,  'name': 'channel4_polarity_read', 'read_only': True },

            # Current
            { 'address': 50,  'name': 'channel1_current_read', 'read_only': True, 'poll': True, 'unit': {'label': 'µA', 'factor': 1000.0} },
            { 'address': 51,  'name': 'channel2_current_read', 'read_only': True, 'poll': True, 'unit': {'label': 'µA', 'factor': 1000.0} },
            { 'address': 52,  'name': 'channel3_current_read', 'read_only': True, 'poll': True, 'unit': {'label': 'µA', 'factor': 1000.0} },
            { 'address': 53,  'name': 'channel4_current_read', 'read_only': True, 'poll': True, 'unit': {'label': 'µA', 'factor': 1000.0} },

            # Misc
            { 'address': 44, 'name': 'rc_enable', 'read_only': True },
            ]
}

def get_device_description():
    return DeviceDescription.fromDict(description_dict)

if __name__ == "__main__":
    import config
    import config_xml
    import logging
    from xml.dom import minidom
    from xml.etree import ElementTree

    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    cfg = config.Config()
    device_description = get_device_description()
    cfg.device_descriptions.append(device_description)

    xml_string = ElementTree.tostring(config_xml.to_etree(cfg).getroot())
    xml_string = minidom.parseString(xml_string).toprettyxml(indent='  ')

    print "DeviceDescription XML for idc=%d, name=%s:" % (device_description.idc, device_description.name)
    print
    print xml_string
    print
    print "Parsing generated XML...",

    parsed_cfg = config_xml.parse_string(xml_string)

    assert len(parsed_cfg.device_descriptions) == 1

    parsed_descr = parsed_cfg.device_descriptions[0]

    assert parsed_descr == device_description

    print "OK!"
