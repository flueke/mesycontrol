#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2021 mesytec GmbH & Co. KG <info@mesytec.com>
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

class VoltageRange(object):
    range_100v = 0
    range_400v = 1

voltage_10   = { 'label': 'V',       'name': 'volt',             'factor': 10.0 }
microamps    = { 'label': 'µA',      'name': 'microamps',        'factor': 1000.0 }
microamps_10 = { 'label': 'µA',      'name': 'microamps',        'factor': 100.0 }

idc = 17

profile_dict = {
        'name': 'MHV-4_v20',
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
            { 'address': 46,  'name': 'channel0_polarity_read', 'index': 0, 'read_only': True, 'poll': True },
            { 'address': 47,  'name': 'channel1_polarity_read', 'index': 1, 'read_only': True, 'poll': True },
            { 'address': 48,  'name': 'channel2_polarity_read', 'index': 2, 'read_only': True, 'poll': True },
            { 'address': 49,  'name': 'channel3_polarity_read', 'index': 3, 'read_only': True, 'poll': True },

            # Current warning limits
            { 'address':  8,  'name': 'channel0_current_limit_write', 'index': 0, 'range': (0, 2000), 'units': [microamps_10], 'default': 2000 },
            { 'address':  9,  'name': 'channel1_current_limit_write', 'index': 1, 'range': (0, 2000), 'units': [microamps_10], 'default': 2000 },
            { 'address': 10,  'name': 'channel2_current_limit_write', 'index': 2, 'range': (0, 2000), 'units': [microamps_10], 'default': 2000 },
            { 'address': 11,  'name': 'channel3_current_limit_write', 'index': 3, 'range': (0, 2000), 'units': [microamps_10], 'default': 2000 },

            { 'address': 40,  'name': 'channel0_current_limit_read', 'index': 0, 'read_only': True, 'poll': True, 'units': [microamps_10] },
            { 'address': 41,  'name': 'channel1_current_limit_read', 'index': 1, 'read_only': True, 'poll': True, 'units': [microamps_10] },
            { 'address': 42,  'name': 'channel2_current_limit_read', 'index': 2, 'read_only': True, 'poll': True, 'units': [microamps_10] },
            { 'address': 43,  'name': 'channel3_current_limit_read', 'index': 3, 'read_only': True, 'poll': True, 'units': [microamps_10] },

            # Current
            { 'address': 50,  'name': 'channel0_current_read', 'index': 0, 'read_only': True, 'poll': True, 'units': [microamps] },
            { 'address': 51,  'name': 'channel1_current_read', 'index': 1, 'read_only': True, 'poll': True, 'units': [microamps] },
            { 'address': 52,  'name': 'channel2_current_read', 'index': 2, 'read_only': True, 'poll': True, 'units': [microamps] },
            { 'address': 53,  'name': 'channel3_current_read', 'index': 3, 'read_only': True, 'poll': True, 'units': [microamps] },

            # Misc
            { 'address': 44,  'name': 'rc_enable', 'read_only': True },
            { 'address': 13,  'name': 'voltage_range_write', 'range': (0, 1), 'default': VoltageRange.range_400v }, # 1=400V, 0=100V
            { 'address': 45,  'name': 'voltage_range_read', 'read_only': True, 'poll': True },

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
