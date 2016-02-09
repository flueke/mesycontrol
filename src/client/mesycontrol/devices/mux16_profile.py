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

idc = 23

profile_dict = {
        'name': 'MUX-16',
        'idc': idc,
        'parameters': [
            # 0=activated, 1=deactivated
            { 'address': 0, 'name': 'deactivate_mux', 'range': (0, 1) },

            # 0=positive, 1=negative
            { 'address': 1, 'name': 'polarity', 'range': (0, 1) },

            # ???
            { 'address': 2, 'name': 'range', 'range': (0, 7) },

            # 4095 is about 80% of full range
            { 'address': 2, 'threshold': 'range', 'range': (0, 4095) },
            ],

        'extensions': [
            ],
}

