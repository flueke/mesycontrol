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

voltage_10  = { 'label': 'V',       'name': 'volt',             'factor': 10.0 }
nanoamps    = { 'label': 'nA',      'name': 'nanoamps', 'offset': -2048 }

idc = 28

NUM_CHANNELS = 16

RAMPS = {
        0: 'down',
        1: 'up'
        }

PREAMP_RANGES = {
        0: 'front panel',
        1: 'high range (low sensitivity)',
        2: 'low range (high sensitivity)'
        }

profile_dict = {
        'name': 'MPRB-16-DR',
        'idc': idc,
        'parameters':

        [ { 'address': i, 'name': 'voltage%d' % i, 'index': i, 'range': (0, 6000), 'units': [voltage_10] }
            for i in range(NUM_CHANNELS) ]
        +
        [
            { 'address': 16, 'name': 'sum_current', 'range': (0, 6000), 'units': [nanoamps], 'read_only': True },
            # 17 is pre-voltage (factory use only)
            { 'address': 18, 'name': 'temperature', 'read_only': True }, # TODO: units
            { 'address': 21, 'name': 'error_code', 'read_only': True },
            { 'address': 22, 'name': 'temp_slope', 'range': (0, 255), 'default': 128 },
            { 'address': 23, 'name': 'temp_offset', 'range': (0, 255), 'default': 128 },
            { 'address': 24, 'name': 'ramp_up_down', 'range': (0, 1) },
            { 'address': 25, 'name': 'voltage_limit', 'range': (0, 6000), 'default': 6000, 'units': [voltage_10] },

            # 0=set by panel switch, 1=high range/low sens, 2=low range/high sens
            { 'address': 26, 'name': 'preamp_range', 'range': (0, 2) },

            # 4 digit firmware revision in BCD format (not implemented)
            #{ 'address': 31, 'name': 'firmware_version', 'read_only': True }
            ],

        'extensions': [
            ],
}
