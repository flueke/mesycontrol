#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from device_profile import DeviceProfile

profile_dict = {
        'name': 'MHV-4-800V',
        'idc': 27,
        'parameters': [
            # Voltage
            { 'address': 0,   'name': 'channel1_voltage_write', 'range': (0, 8000), 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 1,   'name': 'channel2_voltage_write', 'range': (0, 8000), 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 2,   'name': 'channel3_voltage_write', 'range': (0, 8000), 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 3,   'name': 'channel4_voltage_write', 'range': (0, 8000), 'unit': {'label': 'V', 'factor': 10.0 } },

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

            # Voltage limits
            { 'address': 18,  'name': 'channel1_voltage_limit_write', 'range': (0, 8000), 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 19,  'name': 'channel2_voltage_limit_write', 'range': (0, 8000), 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 20,  'name': 'channel3_voltage_limit_write', 'range': (0, 8000), 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 21,  'name': 'channel4_voltage_limit_write', 'range': (0, 8000), 'unit': {'label': 'V', 'factor': 10.0 } },

            { 'address': 22,  'name': 'channel1_voltage_limit_read', 'read_only': True, 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 23,  'name': 'channel2_voltage_limit_read', 'read_only': True, 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 24,  'name': 'channel3_voltage_limit_read', 'read_only': True, 'unit': {'label': 'V', 'factor': 10.0 } },
            { 'address': 25,  'name': 'channel4_voltage_limit_read', 'read_only': True, 'unit': {'label': 'V', 'factor': 10.0 } },

            # Polarity
            { 'address': 14,  'name': 'channel1_polarity_write' },
            { 'address': 15,  'name': 'channel2_polarity_write' },
            { 'address': 16,  'name': 'channel3_polarity_write' },
            { 'address': 17,  'name': 'channel4_polarity_write' },

            { 'address': 46,  'name': 'channel1_polarity_read', 'read_only': True },
            { 'address': 47,  'name': 'channel2_polarity_read', 'read_only': True },
            { 'address': 48,  'name': 'channel3_polarity_read', 'read_only': True },
            { 'address': 49,  'name': 'channel4_polarity_read', 'read_only': True },

            # Current
            { 'address': 50,  'name': 'channel1_current_read', 'read_only': True, 'poll': True, 'unit': {'label': 'µA', 'factor': 1000.0} },
            { 'address': 51,  'name': 'channel2_current_read', 'read_only': True, 'poll': True, 'unit': {'label': 'µA', 'factor': 1000.0} },
            { 'address': 52,  'name': 'channel3_current_read', 'read_only': True, 'poll': True, 'unit': {'label': 'µA', 'factor': 1000.0} },
            { 'address': 53,  'name': 'channel4_current_read', 'read_only': True, 'poll': True, 'unit': {'label': 'µA', 'factor': 1000.0} },

            # Temperature
            { 'address': 26,  'name': 'channel1_temp_read', 'read_only': True, 'unit': {'label': '°C', 'factor': 10.0} },
            { 'address': 27,  'name': 'channel2_temp_read', 'read_only': True, 'unit': {'label': '°C', 'factor': 10.0} },
            { 'address': 28,  'name': 'channel3_temp_read', 'read_only': True, 'unit': {'label': '°C', 'factor': 10.0} },
            { 'address': 29,  'name': 'channel4_temp_read', 'read_only': True, 'unit': {'label': '°C', 'factor': 10.0} },

            # Temperature compensation slope
            { 'address': 64,  'name': 'channel1_tcomp_slope_write', 'range': (0, 19999), 'unit': {'label': 'V/°C', 'factor': 10.0, 'offset': 10000.0} },
            { 'address': 65,  'name': 'channel2_tcomp_slope_write', 'range': (0, 19999), 'unit': {'label': 'V/°C', 'factor': 10.0, 'offset': 10000.0} },
            { 'address': 66,  'name': 'channel3_tcomp_slope_write', 'range': (0, 19999), 'unit': {'label': 'V/°C', 'factor': 10.0, 'offset': 10000.0} },
            { 'address': 67,  'name': 'channel4_tcomp_slope_write', 'range': (0, 19999), 'unit': {'label': 'V/°C', 'factor': 10.0, 'offset': 10000.0} },

            { 'address': 100,  'name': 'channel1_tcomp_slope_read', 'read_only': True, 'unit': {'label': 'V/°C', 'factor': 10.0, 'offset': 10000.0} },
            { 'address': 101,  'name': 'channel2_tcomp_slope_read', 'read_only': True, 'unit': {'label': 'V/°C', 'factor': 10.0, 'offset': 10000.0} },
            { 'address': 102,  'name': 'channel3_tcomp_slope_read', 'read_only': True, 'unit': {'label': 'V/°C', 'factor': 10.0, 'offset': 10000.0} },
            { 'address': 103,  'name': 'channel4_tcomp_slope_read', 'read_only': True, 'unit': {'label': 'V/°C', 'factor': 10.0, 'offset': 10000.0} },

            # Temperature compensation offset
            { 'address': 68,  'name': 'channel1_tcomp_offset_write', 'range': (0, 500), 'unit': {'label': '°C', 'factor': 10.0} },
            { 'address': 69,  'name': 'channel2_tcomp_offset_write', 'range': (0, 500), 'unit': {'label': '°C', 'factor': 10.0} },
            { 'address': 70,  'name': 'channel3_tcomp_offset_write', 'range': (0, 500), 'unit': {'label': '°C', 'factor': 10.0} },
            { 'address': 71,  'name': 'channel4_tcomp_offset_write', 'range': (0, 500), 'unit': {'label': '°C', 'factor': 10.0} },

            { 'address': 104,  'name': 'channel1_tcomp_offset_read', 'read_only': True, 'unit': {'label': '°C', 'factor': 10.0} },
            { 'address': 105,  'name': 'channel2_tcomp_offset_read', 'read_only': True, 'unit': {'label': '°C', 'factor': 10.0} },
            { 'address': 106,  'name': 'channel3_tcomp_offset_read', 'read_only': True, 'unit': {'label': '°C', 'factor': 10.0} },
            { 'address': 107,  'name': 'channel4_tcomp_offset_read', 'read_only': True, 'unit': {'label': '°C', 'factor': 10.0} },

            # Temperature compensation source
            { 'address': 72,  'name': 'channel1_tcomp_source_write', 'range': (0, 4)},
            { 'address': 73,  'name': 'channel2_tcomp_source_write', 'range': (0, 4)},
            { 'address': 74,  'name': 'channel3_tcomp_source_write', 'range': (0, 4)},
            { 'address': 75,  'name': 'channel4_tcomp_source_write', 'range': (0, 4)},

            { 'address': 108,  'name': 'channel1_tcomp_source_read', 'read_only': True},
            { 'address': 109,  'name': 'channel2_tcomp_source_read', 'read_only': True},
            { 'address': 110,  'name': 'channel3_tcomp_source_read', 'read_only': True},
            { 'address': 111,  'name': 'channel4_tcomp_source_read', 'read_only': True},

            # Voltage precision
            { 'address': 76,   'name': 'channel1_voltage_prec_write', 'range': (0, 64000), 'unit': {'label': 'V', 'factor': 80.0 } },
            { 'address': 77,   'name': 'channel2_voltage_prec_write', 'range': (0, 64000), 'unit': {'label': 'V', 'factor': 80.0 } },
            { 'address': 78,   'name': 'channel3_voltage_prec_write', 'range': (0, 64000), 'unit': {'label': 'V', 'factor': 80.0 } },
            { 'address': 79,   'name': 'channel4_voltage_prec_write', 'range': (0, 64000), 'unit': {'label': 'V', 'factor': 80.0 } },

            { 'address': 112,  'name': 'channel1_voltage_prec_read', 'read_only': True, 'poll': True, 'unit': {'label': 'V', 'factor': 80.0 } },
            { 'address': 113,  'name': 'channel2_voltage_prec_read', 'read_only': True, 'poll': True, 'unit': {'label': 'V', 'factor': 80.0 } },
            { 'address': 114,  'name': 'channel3_voltage_prec_read', 'read_only': True, 'poll': True, 'unit': {'label': 'V', 'factor': 80.0 } },
            { 'address': 115,  'name': 'channel4_voltage_prec_read', 'read_only': True, 'poll': True, 'unit': {'label': 'V', 'factor': 80.0 } },

            # Misc
            { 'address': 44,  'name': 'rc_enable', 'read_only': True },
            { 'address': 80,  'name': 'ramp_speed_write', 'range': (0, 3) },
            { 'address': 116, 'name': 'ramp_speed_read', 'read_only': True }
            ]
}

def get_device_profile():
    return DeviceProfile.fromDict(profile_dict)
