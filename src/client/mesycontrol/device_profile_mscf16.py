#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from device_profile import DeviceProfile

profile_dict = {
        'name': 'MSCF-16',
        'idc': 20,
        'parameters': [
            # Gain
            { 'address': 0, 'name': 'gain_group0', 'index': 0, 'range': (0, 15)},
            { 'address': 1, 'name': 'gain_group1', 'index': 1, 'range': (0, 15)},
            { 'address': 2, 'name': 'gain_group2', 'index': 2, 'range': (0, 15)},
            { 'address': 3, 'name': 'gain_group3', 'index': 3, 'range': (0, 15)},
            { 'address': 4, 'name': 'gain_common', 'range': (0, 15)},

            # Threshold
            { 'address':  5, 'name': 'threshold_channel0' , 'index': 0,  'range': (0, 255) },
            { 'address':  6, 'name': 'threshold_channel1' , 'index': 1,  'range': (0, 255) },
            { 'address':  7, 'name': 'threshold_channel2' , 'index': 2,  'range': (0, 255) },
            { 'address':  8, 'name': 'threshold_channel3' , 'index': 3,  'range': (0, 255) },
            { 'address':  9, 'name': 'threshold_channel4' , 'index': 4,  'range': (0, 255) },
            { 'address': 10, 'name': 'threshold_channel5' , 'index': 5,  'range': (0, 255) },
            { 'address': 11, 'name': 'threshold_channel6' , 'index': 6,  'range': (0, 255) },
            { 'address': 12, 'name': 'threshold_channel7' , 'index': 7,  'range': (0, 255) },
            { 'address': 13, 'name': 'threshold_channel8' , 'index': 8,  'range': (0, 255) },
            { 'address': 14, 'name': 'threshold_channel9',  'index': 9,  'range': (0, 255) },
            { 'address': 15, 'name': 'threshold_channel10', 'index': 10, 'range': (0, 255) },
            { 'address': 16, 'name': 'threshold_channel11', 'index': 11, 'range': (0, 255) },
            { 'address': 17, 'name': 'threshold_channel12', 'index': 12, 'range': (0, 255) },
            { 'address': 18, 'name': 'threshold_channel13', 'index': 13, 'range': (0, 255) },
            { 'address': 19, 'name': 'threshold_channel14', 'index': 14, 'range': (0, 255) },
            { 'address': 20, 'name': 'threshold_channel15', 'index': 15, 'range': (0, 255) },
            { 'address': 21, 'name': 'threshold_common'   , 'range': (0, 255) },

            # PZ value
            { 'address': 22, 'name': 'pz_value_channel0' , 'index': 0,  'range': (0, 255) },
            { 'address': 23, 'name': 'pz_value_channel1' , 'index': 1,  'range': (0, 255) },
            { 'address': 24, 'name': 'pz_value_channel2' , 'index': 2,  'range': (0, 255) },
            { 'address': 25, 'name': 'pz_value_channel3' , 'index': 3,  'range': (0, 255) },
            { 'address': 26, 'name': 'pz_value_channel4' , 'index': 4,  'range': (0, 255) },
            { 'address': 27, 'name': 'pz_value_channel5' , 'index': 5,  'range': (0, 255) },
            { 'address': 28, 'name': 'pz_value_channel6' , 'index': 6,  'range': (0, 255) },
            { 'address': 29, 'name': 'pz_value_channel7' , 'index': 7,  'range': (0, 255) },
            { 'address': 30, 'name': 'pz_value_channel8' , 'index': 8,  'range': (0, 255) },
            { 'address': 31, 'name': 'pz_value_channel9',  'index': 9,  'range': (0, 255) },
            { 'address': 32, 'name': 'pz_value_channel10', 'index': 10, 'range': (0, 255) },
            { 'address': 33, 'name': 'pz_value_channel11', 'index': 11, 'range': (0, 255) },
            { 'address': 34, 'name': 'pz_value_channel12', 'index': 12, 'range': (0, 255) },
            { 'address': 35, 'name': 'pz_value_channel13', 'index': 13, 'range': (0, 255) },
            { 'address': 36, 'name': 'pz_value_channel14', 'index': 14, 'range': (0, 255) },
            { 'address': 37, 'name': 'pz_value_channel15', 'index': 15, 'range': (0, 255) },
            { 'address': 38, 'name': 'pz_value_common'   , 'range': (0, 255) },

            # Shaping time
            { 'address': 39, 'name': 'shaping_time_group0', 'index': 0, 'range': (0, 3) },
            { 'address': 40, 'name': 'shaping_time_group1', 'index': 1, 'range': (0, 3) },
            { 'address': 41, 'name': 'shaping_time_group2', 'index': 2, 'range': (0, 3) },
            { 'address': 42, 'name': 'shaping_time_group3', 'index': 3, 'range': (0, 3) },
            { 'address': 43, 'name': 'shaping_time_common', 'range': (0, 3) },

            # Misc
            { 'address': 44, 'name': 'multiplicity_hi', 'range': (0, 8) },
            { 'address': 45, 'name': 'multiplicity_lo', 'range': (0, 8) },
            { 'address': 46, 'name': 'monitor_channel', 'range': (1, 16), 'do_not_store': True },
            { 'address': 47, 'name': 'single_channel_mode', 'range': (0, 1) },
            { 'address': 48, 'name': 'rc_enable', 'read_only': True },
            { 'address': 49, 'name': 'version',   'read_only': True },
            { 'address': 50, 'name': 'blr_threshold', 'range': (0, 255) },
            { 'address': 51, 'name': 'blr_enable', 'range': (0, 1) },
            { 'address': 52, 'name': 'coincidence_time', 'range': (0, 255) },
            { 'address': 53, 'name': 'threshold_offset', 'range': (0, 200) },
            { 'address': 54, 'name': 'shaper_offset'   , 'range': (0, 200) },
            #{ 'address': 55, 'name': 'sumdis_threshold' },  # MSCF-16-LN (special models only)
            #{ 'address': 56, 'name': 'pz_display_range', 'range': (1, 255) },  # MSCF-16-LN
            #{ 'address': 57, 'name': 'ecl_trigger_delay' }, # MSCF-16-F
            #{ 'address': 58, 'name': 'tf_int_time', 'range': (0, 3) },       # MSCF-16-F
            { 'address': 99, 'name': 'copy_function', 'range': (1, 3), 'do_not_store': True },           # MSCF-16-LN
            { 'address':100, 'name': 'auto_pz', 'poll': True, 'do_not_store': True },   # MSCF-16-LN
            ]
}

def get_device_profile():
    return DeviceProfile.fromDict(profile_dict)
