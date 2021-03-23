#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2016 mesytec GmbH & Co. KG <info@mesytec.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

__author__ = 'Florian Lüke'
__email__  = 'f.lueke@mesytec.com'

class Polarity(object):
    negative = 0
    positive = 1

    @staticmethod
    def switch(pol):
        if pol == Polarity.positive:
            return Polarity.negative
        return Polarity.positive


voltage_10  = { 'label': 'V',       'name': 'volt',             'factor': 10.0 }
voltage_80  = { 'label': 'V',       'name': 'volt_prec',        'factor': 80.0 }
tcomp_slope = { 'label': 'V/°C',    'name': 'volt_per_deg',     'factor': 1000.0, 'offset': -10.0 }
microamps   = { 'label': 'µA',      'name': 'microamps',        'factor': 1000.0 }
celcius_10  = { 'label': '°C',      'name': 'degree_celcius',   'factor': 10.0}

idc = 27

profile_dict = {
        'name': 'MHV-4',
        'idc': idc,
        'parameters': [
            # Enable. Mark channel enable setting as critical.
            { 'address': 4,   'name': 'channel0_enable_write', 'index': 0, 'critical': True, 'default': 0 },
            { 'address': 5,   'name': 'channel1_enable_write', 'index': 1, 'critical': True, 'default': 0 },
            { 'address': 6,   'name': 'channel2_enable_write', 'index': 2, 'critical': True, 'default': 0 },
            { 'address': 7,   'name': 'channel3_enable_write', 'index': 3, 'critical': True, 'default': 0 },

            { 'address': 36,  'name': 'channel0_enable_read', 'index': 0, 'read_only': True, 'poll': True },
            { 'address': 37,  'name': 'channel1_enable_read', 'index': 1, 'read_only': True, 'poll': True },
            { 'address': 38,  'name': 'channel2_enable_read', 'index': 2, 'read_only': True, 'poll': True },
            { 'address': 39,  'name': 'channel3_enable_read', 'index': 3, 'read_only': True, 'poll': True },

            # Polarity
            { 'address': 14,  'name': 'channel0_polarity_write', 'index': 0, 'default': Polarity.positive},
            { 'address': 15,  'name': 'channel1_polarity_write', 'index': 1, 'default': Polarity.positive},
            { 'address': 16,  'name': 'channel2_polarity_write', 'index': 2, 'default': Polarity.positive},
            { 'address': 17,  'name': 'channel3_polarity_write', 'index': 3, 'default': Polarity.positive},

            { 'address': 46,  'name': 'channel0_polarity_read', 'index': 0, 'read_only': True, 'poll': True },
            { 'address': 47,  'name': 'channel1_polarity_read', 'index': 1, 'read_only': True, 'poll': True },
            { 'address': 48,  'name': 'channel2_polarity_read', 'index': 2, 'read_only': True, 'poll': True },
            { 'address': 49,  'name': 'channel3_polarity_read', 'index': 3, 'read_only': True, 'poll': True },

            # Voltage limits
            { 'address': 18,  'name': 'channel0_voltage_limit_write', 'index': 0, 'range': (0, 8000), 'units': [voltage_10], 'default': 8000 },
            { 'address': 19,  'name': 'channel1_voltage_limit_write', 'index': 1, 'range': (0, 8000), 'units': [voltage_10], 'default': 8000 },
            { 'address': 20,  'name': 'channel2_voltage_limit_write', 'index': 2, 'range': (0, 8000), 'units': [voltage_10], 'default': 8000 },
            { 'address': 21,  'name': 'channel3_voltage_limit_write', 'index': 3, 'range': (0, 8000), 'units': [voltage_10], 'default': 8000 },

            { 'address': 22,  'name': 'channel0_voltage_limit_read', 'index': 0, 'read_only': True, 'poll': True, 'units': [voltage_10] },
            { 'address': 23,  'name': 'channel1_voltage_limit_read', 'index': 1, 'read_only': True, 'poll': True, 'units': [voltage_10] },
            { 'address': 24,  'name': 'channel2_voltage_limit_read', 'index': 2, 'read_only': True, 'poll': True, 'units': [voltage_10] },
            { 'address': 25,  'name': 'channel3_voltage_limit_read', 'index': 3, 'read_only': True, 'poll': True, 'units': [voltage_10] },

            # Current warning limits
            { 'address':  8,  'name': 'channel0_current_limit_write', 'index': 0, 'range': (0, 20000), 'units': [microamps], 'default': 20000 },
            { 'address':  9,  'name': 'channel1_current_limit_write', 'index': 1, 'range': (0, 20000), 'units': [microamps], 'default': 20000 },
            { 'address': 10,  'name': 'channel2_current_limit_write', 'index': 2, 'range': (0, 20000), 'units': [microamps], 'default': 20000 },
            { 'address': 11,  'name': 'channel3_current_limit_write', 'index': 3, 'range': (0, 20000), 'units': [microamps], 'default': 20000 },

            { 'address': 40,  'name': 'channel0_current_limit_read', 'index': 0, 'read_only': True, 'poll': True, 'units': [microamps] },
            { 'address': 41,  'name': 'channel1_current_limit_read', 'index': 1, 'read_only': True, 'poll': True, 'units': [microamps] },
            { 'address': 42,  'name': 'channel2_current_limit_read', 'index': 2, 'read_only': True, 'poll': True, 'units': [microamps] },
            { 'address': 43,  'name': 'channel3_current_limit_read', 'index': 3, 'read_only': True, 'poll': True, 'units': [microamps] },

            # Current
            { 'address': 50,  'name': 'channel0_current_read', 'index': 0, 'read_only': True, 'poll': True, 'units': [microamps] },
            { 'address': 51,  'name': 'channel1_current_read', 'index': 1, 'read_only': True, 'poll': True, 'units': [microamps] },
            { 'address': 52,  'name': 'channel2_current_read', 'index': 2, 'read_only': True, 'poll': True, 'units': [microamps] },
            { 'address': 53,  'name': 'channel3_current_read', 'index': 3, 'read_only': True, 'poll': True, 'units': [microamps] },

            # Temperature
            { 'address': 26,  'name': 'sensor0_temp_read', 'index': 0, 'read_only': True, 'poll': True, 'units': [celcius_10] },
            { 'address': 27,  'name': 'sensor1_temp_read', 'index': 1, 'read_only': True, 'poll': True, 'units': [celcius_10] },
            { 'address': 28,  'name': 'sensor2_temp_read', 'index': 2, 'read_only': True, 'poll': True, 'units': [celcius_10] },
            { 'address': 29,  'name': 'sensor3_temp_read', 'index': 3, 'read_only': True, 'poll': True, 'units': [celcius_10] },

            # Temperature compensation slope
            { 'address': 64,  'name': 'channel0_tcomp_slope_write', 'index': 0, 'range': (0, 19999), 'units': [tcomp_slope], 'default': 10000 },
            { 'address': 65,  'name': 'channel1_tcomp_slope_write', 'index': 1, 'range': (0, 19999), 'units': [tcomp_slope], 'default': 10000 },
            { 'address': 66,  'name': 'channel2_tcomp_slope_write', 'index': 2, 'range': (0, 19999), 'units': [tcomp_slope], 'default': 10000 },
            { 'address': 67,  'name': 'channel3_tcomp_slope_write', 'index': 3, 'range': (0, 19999), 'units': [tcomp_slope], 'default': 10000 },

            { 'address': 100,  'name': 'channel0_tcomp_slope_read', 'index': 0, 'read_only': True, 'poll': True, 'units': [tcomp_slope] },
            { 'address': 101,  'name': 'channel1_tcomp_slope_read', 'index': 1, 'read_only': True, 'poll': True, 'units': [tcomp_slope] },
            { 'address': 102,  'name': 'channel2_tcomp_slope_read', 'index': 2, 'read_only': True, 'poll': True, 'units': [tcomp_slope] },
            { 'address': 103,  'name': 'channel3_tcomp_slope_read', 'index': 3, 'read_only': True, 'poll': True, 'units': [tcomp_slope] },

            # Temperature compensation offset
            { 'address': 68,  'name': 'channel0_tcomp_offset_write', 'index': 0, 'range': (0, 500), 'units': [celcius_10], 'default': 0 },
            { 'address': 69,  'name': 'channel1_tcomp_offset_write', 'index': 1, 'range': (0, 500), 'units': [celcius_10], 'default': 0 },
            { 'address': 70,  'name': 'channel2_tcomp_offset_write', 'index': 2, 'range': (0, 500), 'units': [celcius_10], 'default': 0 },
            { 'address': 71,  'name': 'channel3_tcomp_offset_write', 'index': 3, 'range': (0, 500), 'units': [celcius_10], 'default': 0 },

            { 'address': 104,  'name': 'channel0_tcomp_offset_read', 'index': 0, 'read_only': True, 'poll': True, 'units': [celcius_10] },
            { 'address': 105,  'name': 'channel1_tcomp_offset_read', 'index': 1, 'read_only': True, 'poll': True, 'units': [celcius_10] },
            { 'address': 106,  'name': 'channel2_tcomp_offset_read', 'index': 2, 'read_only': True, 'poll': True, 'units': [celcius_10] },
            { 'address': 107,  'name': 'channel3_tcomp_offset_read', 'index': 3, 'read_only': True, 'poll': True, 'units': [celcius_10] },

            # Temperature compensation source
            { 'address': 72,  'name': 'channel0_tcomp_source_write', 'index': 0, 'range': (0, 4), 'default': 4},
            { 'address': 73,  'name': 'channel1_tcomp_source_write', 'index': 1, 'range': (0, 4), 'default': 4},
            { 'address': 74,  'name': 'channel2_tcomp_source_write', 'index': 2, 'range': (0, 4), 'default': 4},
            { 'address': 75,  'name': 'channel3_tcomp_source_write', 'index': 3, 'range': (0, 4), 'default': 4},

            { 'address': 108,  'name': 'channel0_tcomp_source_read', 'index': 0, 'read_only': True, 'poll': True},
            { 'address': 109,  'name': 'channel1_tcomp_source_read', 'index': 1, 'read_only': True, 'poll': True},
            { 'address': 110,  'name': 'channel2_tcomp_source_read', 'index': 2, 'read_only': True, 'poll': True},
            { 'address': 111,  'name': 'channel3_tcomp_source_read', 'index': 3, 'read_only': True, 'poll': True},

            # Voltage precision
            # Set to not be stored/loaded as this interferes with channelN_voltage_write.
            { 'address': 76,   'name': 'channel0_voltage_prec_write', 'index': 0, 'range': (0, 64000), 'units': [voltage_80], 'do_not_store': True },
            { 'address': 77,   'name': 'channel1_voltage_prec_write', 'index': 1, 'range': (0, 64000), 'units': [voltage_80], 'do_not_store': True },
            { 'address': 78,   'name': 'channel2_voltage_prec_write', 'index': 2, 'range': (0, 64000), 'units': [voltage_80], 'do_not_store': True },
            { 'address': 79,   'name': 'channel3_voltage_prec_write', 'index': 3, 'range': (0, 64000), 'units': [voltage_80], 'do_not_store': True },

            { 'address': 112,  'name': 'channel0_voltage_prec_read', 'index': 0, 'read_only': True, 'poll': True, 'units': [voltage_80] },
            { 'address': 113,  'name': 'channel1_voltage_prec_read', 'index': 1, 'read_only': True, 'poll': True, 'units': [voltage_80] },
            { 'address': 114,  'name': 'channel2_voltage_prec_read', 'index': 2, 'read_only': True, 'poll': True, 'units': [voltage_80] },
            { 'address': 115,  'name': 'channel3_voltage_prec_read', 'index': 3, 'read_only': True, 'poll': True, 'units': [voltage_80] },

            # Misc
            { 'address': 44,  'name': 'rc_enable', 'read_only': True },
            { 'address': 80,  'name': 'ramp_speed_write', 'range': (0, 3), 'default': 0 },
            { 'address': 116, 'name': 'ramp_speed_read', 'read_only': True, 'poll': True },

            # Voltage
            # Keep at the end of the parameter list to make sure these
            # addresses are written last when loading a config.
            { 'address': 0,   'name': 'channel0_voltage_write', 'index': 0, 'range': (0, 8000), 'units': [voltage_10], 'default': 0 },
            { 'address': 1,   'name': 'channel1_voltage_write', 'index': 1, 'range': (0, 8000), 'units': [voltage_10], 'default': 0 },
            { 'address': 2,   'name': 'channel2_voltage_write', 'index': 2, 'range': (0, 8000), 'units': [voltage_10], 'default': 0 },
            { 'address': 3,   'name': 'channel3_voltage_write', 'index': 3, 'range': (0, 8000), 'units': [voltage_10], 'default': 0 },

            { 'address': 32,  'name': 'channel0_voltage_read', 'index': 0, 'read_only': True, 'poll': True, 'units': [voltage_10] },
            { 'address': 33,  'name': 'channel1_voltage_read', 'index': 1, 'read_only': True, 'poll': True, 'units': [voltage_10] },
            { 'address': 34,  'name': 'channel2_voltage_read', 'index': 2, 'read_only': True, 'poll': True, 'units': [voltage_10] },
            { 'address': 35,  'name': 'channel3_voltage_read', 'index': 3, 'read_only': True, 'poll': True, 'units': [voltage_10] },
            ]
}
