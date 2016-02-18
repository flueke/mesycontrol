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

idc = 21

NUM_CHANNELS = 4

OUTPUT_RANGES  = {
        0: '4 V',
        1: '8 V'
        }

OUTPUT_SOURCES = {
        0: 'neutrons',
        1: 'gammas',
        2: 'reject',
        3: 'all (n+g)'
        }

profile_dict = {
        'name': 'MPD-4',
        'idc': idc,
        'parameters':
        [ { 'address': i, 'name': 'gain%d' % i, 'index': i, 'range': (0, 15) } for i in range(NUM_CHANNELS) ]
        +
        # TAC shift, neutron discriminator
        [ { 'address': i+4, 'name': 'ndis%d' % i, 'index': i, 'range': (0, 255) } for i in range(NUM_CHANNELS) ]
        +
        # 100=no correction
        [ { 'address': i+8, 'name': 'qwin%d' % i, 'index': i, 'range': (0, 200) } for i in range(NUM_CHANNELS) ]
        +
        [ { 'address': i+12, 'name': 'threshold%d' % i, 'index': i, 'range': (0, 255) } for i in range(NUM_CHANNELS) ]
        +
        # offset to factory walk correction, 100=no offset
        [ { 'address': i+16, 'name': 'walk%d' % i, 'index': i, 'range': (50, 150) } for i in range(NUM_CHANNELS) ]
        +
        [
            # 0=slow mode, 1=fast mode
            { 'address': 23, 'name': 'fast_mode', 'range': (0, 1) },

            # 0=4V, 1=8V
            { 'address': 25, 'name': 'output_range', 'range': (0, 1), 'read_only': True },

            # 0=neutrons, 1=gammas, 2=reject, 3=all
            { 'address': 40, 'name': 'output_source', 'range': (0, 3) },
            ],

        'extensions': [
            ],
        }
