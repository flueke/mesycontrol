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

idc = 24

NUM_CHANNELS = 8

OUTPUT_SOURCES = {
        0: 'neutrons',
        1: 'gammas',
        2: 'reject',
        3: 'all (n+g)'
        }

profile_dict = {
        'name': 'MPD-8',
        'idc': idc,
        'parameters':
        [ { 'address': i, 'name': 'ndis%d' % i, 'index': i, 'range': (0, 255) } for i in range(NUM_CHANNELS) ]
        +
        [ { 'address': i+8,  'name': 'walk%d' % i, 'index': i, 'range': (0, 200) } for i in range(NUM_CHANNELS) ]
        +
        [
            { 'address': 16, 'name': 'threshold_common', 'range': (0, 255) },
            { 'address': 32, 'name': 'gain_common', 'range': (0, 3) },

            # 0=slow mode, 1=fast mode
            { 'address': 33, 'name': 'fast_mode', 'range': (0, 1) },

            # 0=neutrons, 1=gammas, 2=reject, 3=all
            { 'address': 34, 'name': 'output_source_a', 'range': (0, 3), 'default': 3 },

            # 0=neutrons, 1=reject
            { 'address': 35, 'name': 'output_source_b', 'range': (0, 3), 'default': 3 },

            # 100=no correction
            { 'address': 48, 'name': 'qwin0', 'index': 0, 'range': (0, 200) },
            ],

        'extensions': [
            ],
        }
