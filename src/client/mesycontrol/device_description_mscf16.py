#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from device_description import DeviceDescription

description_dict = {
        'name': 'MSCF-16',
        'idc': 20,
        'parameters': [
            # Gain
            { 'address': 0, 'name': 'gain_group1', 'range': (0, 15)},
            { 'address': 1, 'name': 'gain_group2', 'range': (0, 15)},
            { 'address': 2, 'name': 'gain_group3', 'range': (0, 15)},
            { 'address': 3, 'name': 'gain_group4', 'range': (0, 15)},
            { 'address': 4, 'name': 'gain_common', 'range': (0, 15)},

            # Threshold
            { 'address':  5, 'name': 'threshold_channel1' , 'range': (0, 255) },
            { 'address':  6, 'name': 'threshold_channel2' , 'range': (0, 255) },
            { 'address':  7, 'name': 'threshold_channel3' , 'range': (0, 255) },
            { 'address':  8, 'name': 'threshold_channel4' , 'range': (0, 255) },
            { 'address':  9, 'name': 'threshold_channel5' , 'range': (0, 255) },
            { 'address': 10, 'name': 'threshold_channel6' , 'range': (0, 255) },
            { 'address': 11, 'name': 'threshold_channel7' , 'range': (0, 255) },
            { 'address': 12, 'name': 'threshold_channel8' , 'range': (0, 255) },
            { 'address': 13, 'name': 'threshold_channel9' , 'range': (0, 255) },
            { 'address': 14, 'name': 'threshold_channel10', 'range': (0, 255) },
            { 'address': 15, 'name': 'threshold_channel11', 'range': (0, 255) },
            { 'address': 16, 'name': 'threshold_channel12', 'range': (0, 255) },
            { 'address': 17, 'name': 'threshold_channel13', 'range': (0, 255) },
            { 'address': 18, 'name': 'threshold_channel14', 'range': (0, 255) },
            { 'address': 19, 'name': 'threshold_channel15', 'range': (0, 255) },
            { 'address': 20, 'name': 'threshold_channel16', 'range': (0, 255) },
            { 'address': 21, 'name': 'threshold_common'   , 'range': (0, 255) },

            # PZ value
            { 'address': 22, 'name': 'pz_value_channel1' , 'range': (0, 255) },
            { 'address': 23, 'name': 'pz_value_channel2' , 'range': (0, 255) },
            { 'address': 24, 'name': 'pz_value_channel3' , 'range': (0, 255) },
            { 'address': 25, 'name': 'pz_value_channel4' , 'range': (0, 255) },
            { 'address': 26, 'name': 'pz_value_channel5' , 'range': (0, 255) },
            { 'address': 27, 'name': 'pz_value_channel6' , 'range': (0, 255) },
            { 'address': 28, 'name': 'pz_value_channel7' , 'range': (0, 255) },
            { 'address': 29, 'name': 'pz_value_channel8' , 'range': (0, 255) },
            { 'address': 30, 'name': 'pz_value_channel9' , 'range': (0, 255) },
            { 'address': 31, 'name': 'pz_value_channel10', 'range': (0, 255) },
            { 'address': 32, 'name': 'pz_value_channel11', 'range': (0, 255) },
            { 'address': 33, 'name': 'pz_value_channel12', 'range': (0, 255) },
            { 'address': 34, 'name': 'pz_value_channel13', 'range': (0, 255) },
            { 'address': 35, 'name': 'pz_value_channel14', 'range': (0, 255) },
            { 'address': 36, 'name': 'pz_value_channel15', 'range': (0, 255) },
            { 'address': 37, 'name': 'pz_value_channel16', 'range': (0, 255) },
            { 'address': 38, 'name': 'pz_value_common'   , 'range': (0, 255) },

            # Shaping time
            { 'address': 39, 'name': 'shaping_time_group1', 'range': (0, 3) },
            { 'address': 40, 'name': 'shaping_time_group2', 'range': (0, 3) },
            { 'address': 41, 'name': 'shaping_time_group3', 'range': (0, 3) },
            { 'address': 42, 'name': 'shaping_time_group4', 'range': (0, 3) },
            { 'address': 43, 'name': 'shaping_time_common', 'range': (0, 3) },

            # Misc
            { 'address': 44, 'name': 'multiplicity_hi', 'range': (0, 8) },
            { 'address': 45, 'name': 'multiplicity_lo', 'range': (0, 8) },
            { 'address': 46, 'name': 'monitor_channel', 'range': (1, 16) },
            { 'address': 47, 'name': 'single_channel_mode', 'range': (0, 1) },
            { 'address': 48, 'name': 'rc_enable', 'read_only': True },
            { 'address': 49, 'name': 'version',   'read_only': True },
            { 'address': 50, 'name': 'blr_threshold', 'range': (0, 255) },
            { 'address': 51, 'name': 'blr_enable', 'range': (0, 1) },
            { 'address': 52, 'name': 'coincidence_time', 'range': (0, 255) },
            { 'address': 53, 'name': 'threshold_offset', 'range': (0, 200) },
            { 'address': 54, 'name': 'shaper_offset'   , 'range': (0, 200) },
            { 'address': 55, 'name': 'sumdis_threshold' },  # MSCF-16-LN (special models only)
            { 'address': 56, 'name': 'pz_display_range', 'range': (1, 255) },  # MSCF-16-LN
            { 'address': 57, 'name': 'ecl_trigger_delay' }, # MSCF-16-F
            { 'address': 58, 'name': 'tf_int_time' },       # MSCF-16-F
            { 'address': 99, 'name': 'copy_function', 'do_not_store': True },           # MSCF-16-LN
            { 'address':100, 'name': 'auto_pz', 'poll': True, 'do_not_store': True },   # MSCF-16-LN
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
