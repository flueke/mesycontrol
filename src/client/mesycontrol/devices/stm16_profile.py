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
__email__  = 'florianlueke@gmx.net'

threshold_percent = { 'label': '%', 'name': 'percent', 'factor': 256/40.0 }

idc = 19

profile_dict = {
        'name': 'STM-16+',
        'idc': idc,
        'parameters': [
            # Gain
            { 'address': 0,  'name': 'gain_group0', 'index': 0, 'range': (0, 15)},
            { 'address': 4,  'name': 'gain_group1', 'index': 1, 'range': (0, 15)},
            { 'address': 8,  'name': 'gain_group2', 'index': 2, 'range': (0, 15)},
            { 'address': 12, 'name': 'gain_group3', 'index': 3, 'range': (0, 15)},
            { 'address': 16, 'name': 'gain_group4', 'index': 4, 'range': (0, 15)},
            { 'address': 20, 'name': 'gain_group5', 'index': 5, 'range': (0, 15)},
            { 'address': 24, 'name': 'gain_group6', 'index': 6, 'range': (0, 15)},
            { 'address': 28, 'name': 'gain_group7', 'index': 7, 'range': (0, 15)},

            # Threshold
            { 'address':  1,  'name': 'threshold_channel0'  , 'index': 0,   'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  3,  'name': 'threshold_channel1'  , 'index': 1,   'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  5,  'name': 'threshold_channel2'  , 'index': 2,   'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  7,  'name': 'threshold_channel3'  , 'index': 3,   'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  9,  'name': 'threshold_channel4'  , 'index': 4,   'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  11, 'name': 'threshold_channel5'  , 'index': 5,   'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  13, 'name': 'threshold_channel6'  , 'index': 6,   'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  15, 'name': 'threshold_channel7'  , 'index': 7,   'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  17, 'name': 'threshold_channel8'  , 'index': 8,   'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  19, 'name': 'threshold_channel9'  , 'index': 9,   'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  21, 'name': 'threshold_channel10' , 'index': 10,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  23, 'name': 'threshold_channel11' , 'index': 11,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  25, 'name': 'threshold_channel12' , 'index': 12,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  27, 'name': 'threshold_channel13' , 'index': 13,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  29, 'name': 'threshold_channel14' , 'index': 14,  'range': (0, 255), 'units': [threshold_percent] },
            { 'address':  31, 'name': 'threshold_channel15' , 'index': 15,  'range': (0, 255), 'units': [threshold_percent] },
            ],

        'extensions': [
            { 'name': 'gain_adjust', 'value': 1 }
            ],
}
