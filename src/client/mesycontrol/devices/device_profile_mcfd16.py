#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from device_profile import DeviceProfile

# TODO: liste der komischen dinge:
# - rc_bit und scanbus output unterscheiden sich wenn am frontpanel werte veraendert wurden. ??? unklar ???
# - discriminator_mode wechsel: LE -> CFD: fast_veto wird aktiviert, CFD -> LE: fast_veto wird deaktiviert

profile_dict = {
        'name': 'MCFD-16',
        'idc': 26,
        'parameters': [
            # Threshold
            { 'address':  0, 'name': 'threshold_channel0' , 'index': 0,  'range': (0, 255) },
            { 'address':  1, 'name': 'threshold_channel1' , 'index': 1,  'range': (0, 255) },
            { 'address':  2, 'name': 'threshold_channel2' , 'index': 2,  'range': (0, 255) },
            { 'address':  3, 'name': 'threshold_channel3' , 'index': 3,  'range': (0, 255) },
            { 'address':  4, 'name': 'threshold_channel4' , 'index': 4,  'range': (0, 255) },
            { 'address':  5, 'name': 'threshold_channel5' , 'index': 5,  'range': (0, 255) },
            { 'address':  6, 'name': 'threshold_channel6' , 'index': 6,  'range': (0, 255) },
            { 'address':  7, 'name': 'threshold_channel7' , 'index': 7,  'range': (0, 255) },
            { 'address':  8, 'name': 'threshold_channel8' , 'index': 8,  'range': (0, 255) },
            { 'address':  9, 'name': 'threshold_channel9',  'index': 9,  'range': (0, 255) },
            { 'address': 10, 'name': 'threshold_channel10', 'index': 10, 'range': (0, 255) },
            { 'address': 11, 'name': 'threshold_channel11', 'index': 11, 'range': (0, 255) },
            { 'address': 12, 'name': 'threshold_channel12', 'index': 12, 'range': (0, 255) },
            { 'address': 13, 'name': 'threshold_channel13', 'index': 13, 'range': (0, 255) },
            { 'address': 14, 'name': 'threshold_channel14', 'index': 14, 'range': (0, 255) },
            { 'address': 15, 'name': 'threshold_channel15', 'index': 15, 'range': (0, 255) },
            { 'address': 64, 'name': 'threshold_common'   ,              'range': (0, 255) },

            # Gain
            { 'address': 16, 'name': 'gain_group0' , 'index': 0,  'range': (0, 2) },
            { 'address': 17, 'name': 'gain_group1' , 'index': 1,  'range': (0, 2) },
            { 'address': 18, 'name': 'gain_group2' , 'index': 2,  'range': (0, 2) },
            { 'address': 19, 'name': 'gain_group3' , 'index': 3,  'range': (0, 2) },
            { 'address': 20, 'name': 'gain_group4' , 'index': 4,  'range': (0, 2) },
            { 'address': 21, 'name': 'gain_group5' , 'index': 5,  'range': (0, 2) },
            { 'address': 22, 'name': 'gain_group6' , 'index': 6,  'range': (0, 2) },
            { 'address': 23, 'name': 'gain_group7' , 'index': 7,  'range': (0, 2) },
            { 'address': 65, 'name': 'gain_common',               'range': (0, 2) },

            # Width
            { 'address': 24, 'name': 'width_group0' , 'index': 0,  'range': (16, 222) },
            { 'address': 25, 'name': 'width_group1' , 'index': 1,  'range': (16, 222) },
            { 'address': 26, 'name': 'width_group2' , 'index': 2,  'range': (16, 222) },
            { 'address': 27, 'name': 'width_group3' , 'index': 3,  'range': (16, 222) },
            { 'address': 28, 'name': 'width_group4' , 'index': 4,  'range': (16, 222) },
            { 'address': 29, 'name': 'width_group5' , 'index': 5,  'range': (16, 222) },
            { 'address': 30, 'name': 'width_group6' , 'index': 6,  'range': (16, 222) },
            { 'address': 31, 'name': 'width_group7' , 'index': 7,  'range': (16, 222) },
            { 'address': 66, 'name': 'width_common',               'range': (16, 222) },

            # Deadtime
            { 'address': 32, 'name': 'deadtime_group0' , 'index': 0,  'range': (27, 222) },
            { 'address': 33, 'name': 'deadtime_group1' , 'index': 1,  'range': (27, 222) },
            { 'address': 34, 'name': 'deadtime_group2' , 'index': 2,  'range': (27, 222) },
            { 'address': 35, 'name': 'deadtime_group3' , 'index': 3,  'range': (27, 222) },
            { 'address': 36, 'name': 'deadtime_group4' , 'index': 4,  'range': (27, 222) },
            { 'address': 37, 'name': 'deadtime_group5' , 'index': 5,  'range': (27, 222) },
            { 'address': 38, 'name': 'deadtime_group6' , 'index': 6,  'range': (27, 222) },
            { 'address': 39, 'name': 'deadtime_group7' , 'index': 7,  'range': (27, 222) },
            { 'address': 67, 'name': 'deadtime_common',               'range': (27, 222) },

            # Delay
            { 'address': 40, 'name': 'delay_group0' , 'index': 0,  'range': (0, 4) },
            { 'address': 41, 'name': 'delay_group1' , 'index': 1,  'range': (0, 4) },
            { 'address': 42, 'name': 'delay_group2' , 'index': 2,  'range': (0, 4) },
            { 'address': 43, 'name': 'delay_group3' , 'index': 3,  'range': (0, 4) },
            { 'address': 44, 'name': 'delay_group4' , 'index': 4,  'range': (0, 4) },
            { 'address': 45, 'name': 'delay_group5' , 'index': 5,  'range': (0, 4) },
            { 'address': 46, 'name': 'delay_group6' , 'index': 6,  'range': (0, 4) },
            { 'address': 47, 'name': 'delay_group7' , 'index': 7,  'range': (0, 4) },
            { 'address': 68, 'name': 'delay_common',               'range': (0, 4) },

            # Fraction
            { 'address': 48, 'name': 'fraction_group0' , 'index': 0,  'range': (0, 1) },
            { 'address': 49, 'name': 'fraction_group1' , 'index': 1,  'range': (0, 1) },
            { 'address': 50, 'name': 'fraction_group2' , 'index': 2,  'range': (0, 1) },
            { 'address': 51, 'name': 'fraction_group3' , 'index': 3,  'range': (0, 1) },
            { 'address': 52, 'name': 'fraction_group4' , 'index': 4,  'range': (0, 1) },
            { 'address': 53, 'name': 'fraction_group5' , 'index': 5,  'range': (0, 1) },
            { 'address': 54, 'name': 'fraction_group6' , 'index': 6,  'range': (0, 1) },
            { 'address': 55, 'name': 'fraction_group7' , 'index': 7,  'range': (0, 1) },
            { 'address': 69, 'name': 'fraction_common',               'range': (0, 1) },

            # Polarity
            { 'address': 56, 'name': 'polarity_group0' , 'index': 0,  'range': (0, 1) },
            { 'address': 57, 'name': 'polarity_group1' , 'index': 1,  'range': (0, 1) },
            { 'address': 58, 'name': 'polarity_group2' , 'index': 2,  'range': (0, 1) },
            { 'address': 59, 'name': 'polarity_group3' , 'index': 3,  'range': (0, 1) },
            { 'address': 60, 'name': 'polarity_group4' , 'index': 4,  'range': (0, 1) },
            { 'address': 61, 'name': 'polarity_group5' , 'index': 5,  'range': (0, 1) },
            { 'address': 62, 'name': 'polarity_group6' , 'index': 6,  'range': (0, 1) },
            { 'address': 63, 'name': 'polarity_group7' , 'index': 7,  'range': (0, 1) },
            { 'address': 70, 'name': 'polarity_common',               'range': (0, 1) },

            # Bandwidth limit
            { 'address': 71, 'name': 'bwl_enable', 'range': (0, 1) }, # cpu firmware version >= 2.18

            # Mode & RC
            { 'address': 72, 'name': 'single_channel_mode',     'range': (0, 1) },
            { 'address': 73, 'name': 'rc', 'read_only': True, 'poll': True,   'range': (0, 1) }, # Marked as read only to avoid storing/loading it

            # Timing parameters
            { 'address': 74, 'name': 'gg_leading_edge_delay',           'range': (5, 255) },
            { 'address': 75, 'name': 'gg_trailing_edge_delay',          'range': (5, 255) },
            { 'address': 76, 'name': 'coincidence_time',                'range': (0, 136) }, # [0, 3..136] -> 1,2 not valid
            { 'address': 77, 'name': 'fast_veto',                       'range': (0, 1) },  # Changes on discriminator_mode change

            # TODO: verify
            # Rate measurement
            # How rate measurement works:
            # Set time_base to one of MCFD16.time_base_secs values to set the
            # duration of one measurement.
            # Once measurement_ready is 1 read frequency_low_byte and
            # frequency_high_byte to get the value. Reading frequency_high_byte
            # will also start a new measurement.
            #
            # [0..15] : signal channels
            # [16..18]: trig0..trig2
            # 19      : total rate
            { 'address': 78, 'name': 'rate_monitor_channel', 'range': (0, 19) },
            { 'address': 79, 'name': 'time_base',           'range': (0, 15) }, 
            { 'address': 80, 'name': 'measurement_ready',   'read_only': True, 'poll': True },
            { 'address': 81, 'name': 'frequency_low_byte',  'read_only': True },
            { 'address': 82, 'name': 'frequency_high_byte', 'read_only': True },

            # Channel mask
            # Bit n masks the channel pair (n, n+1)
            { 'address': 83, 'name': 'channel_mask',           'range': (0, 255) }, 

            # Discriminator mode
            { 'address': 85, 'name': 'discriminator_mode', 'range': (0, 1) },   # cpu firmware version >= 2.18, 0=LE, 1=CFD

            # Test pulser
            # (off, 2.5MHz, 1.22kHz)
            { 'address': 118, 'name': 'test_pulser', 'range': (0, 2) },

            # Monitor outputs
            # channel -> monitor assignment
            { 'address': 122, 'name': 'monitor0', 'range': (0, 15) },
            { 'address': 123, 'name': 'monitor1', 'range': (0, 15) },

            # Trigger pattern
            { 'address': 124, 'name': 'trigger_pattern0_low' , 'index': 0, 'range': (0, 255) },
            { 'address': 125, 'name': 'trigger_pattern0_high', 'index': 0, 'range': (0, 255) },
            { 'address': 126, 'name': 'trigger_pattern1_low' , 'index': 1, 'range': (0, 255) },
            { 'address': 127, 'name': 'trigger_pattern1_high', 'index': 1, 'range': (0, 255) },

            # Trigger sources
            { 'address': 128, 'name': 'trigger0', 'index': 0, 'range': (0, 255) },
            { 'address': 129, 'name': 'trigger1', 'index': 1, 'range': (0, 255) },
            { 'address': 130, 'name': 'trigger2', 'index': 2, 'range': (0, 255) },

            # Gate gen sources
            { 'address': 131, 'name': 'gg_sources', 'range': (0, 127) },

            # Multiplicity
            { 'address': 132, 'name': 'multiplicity_lo', 'range': (1, 16) },
            { 'address': 133, 'name': 'multiplicity_hi', 'range': (1, 16) },

            # Pair coincidence pattern
            { 'address': 134, 'name': 'pair_pattern0_low',  'index': 0 , 'range': (0, 255)     },
            { 'address': 135, 'name': 'pair_pattern0_high', 'index': 0 , 'range': (0, 255)     },
            { 'address': 136, 'name': 'pair_pattern1_low',  'index': 1 , 'range': (0, 255)     },
            { 'address': 137, 'name': 'pair_pattern1_high', 'index': 1 , 'range': (0, 255)     },
            { 'address': 138, 'name': 'pair_pattern2_low',  'index': 2 , 'range': (0, 255)     },
            { 'address': 139, 'name': 'pair_pattern2_high', 'index': 2 , 'range': (0, 255)     },
            { 'address': 140, 'name': 'pair_pattern3_low',  'index': 3 , 'range': (0, 255)     },
            { 'address': 141, 'name': 'pair_pattern3_high', 'index': 3 , 'range': (0, 255)     },
            { 'address': 142, 'name': 'pair_pattern4_low',  'index': 4 , 'range': (0, 255)     },
            { 'address': 143, 'name': 'pair_pattern4_high', 'index': 4 , 'range': (0, 255)     },
            { 'address': 144, 'name': 'pair_pattern5_low',  'index': 5 , 'range': (0, 255)     },
            { 'address': 145, 'name': 'pair_pattern5_high', 'index': 5 , 'range': (0, 255)     },
            { 'address': 146, 'name': 'pair_pattern6_low',  'index': 6 , 'range': (0, 255)     },
            { 'address': 147, 'name': 'pair_pattern6_high', 'index': 6 , 'range': (0, 255)     },
            { 'address': 148, 'name': 'pair_pattern7_low',  'index': 7 , 'range': (0, 255)     },
            { 'address': 149, 'name': 'pair_pattern7_high', 'index': 7 , 'range': (0, 255)     },
            { 'address': 150, 'name': 'pair_pattern8_low',  'index': 8 , 'range': (0, 255)     },
            { 'address': 151, 'name': 'pair_pattern8_high', 'index': 8 , 'range': (0, 255)     },
            { 'address': 152, 'name': 'pair_pattern9_low',  'index': 9 , 'range': (0, 255)     },
            { 'address': 153, 'name': 'pair_pattern9_high', 'index': 9 , 'range': (0, 255)     },
            { 'address': 154, 'name': 'pair_pattern10_low', 'index': 10, 'range': (0, 255)     },
            { 'address': 155, 'name': 'pair_pattern10_high','index': 10, 'range': (0, 255)     },
            { 'address': 156, 'name': 'pair_pattern11_low', 'index': 11, 'range': (0, 255)     },
            { 'address': 157, 'name': 'pair_pattern11_high','index': 11, 'range': (0, 255)     },
            { 'address': 158, 'name': 'pair_pattern12_low', 'index': 12, 'range': (0, 255)     },
            { 'address': 159, 'name': 'pair_pattern12_high','index': 12, 'range': (0, 255)     },
            { 'address': 160, 'name': 'pair_pattern13_low', 'index': 13, 'range': (0, 255)     },
            { 'address': 161, 'name': 'pair_pattern13_high','index': 13, 'range': (0, 255)     },
            { 'address': 162, 'name': 'pair_pattern14_low', 'index': 14, 'range': (0, 255)     },
            { 'address': 163, 'name': 'pair_pattern14_high','index': 14, 'range': (0, 255)     },
            { 'address': 164, 'name': 'pair_pattern15_low', 'index': 15, 'range': (0, 255)     },
            { 'address': 165, 'name': 'pair_pattern15_high','index': 15, 'range': (0, 255)     },

            { 'address': 254, 'name': 'fpga_firmware_version', 'read_only': True },
            { 'address': 255, 'name': 'cpu_firmware_version', 'read_only': True },
            ]
}

def get_device_profile():
    return DeviceProfile.fromDict(profile_dict)
