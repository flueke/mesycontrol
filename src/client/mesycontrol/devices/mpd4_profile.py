#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

idc = 21

profile_dict = {
        'name': 'MPD-4',
        'idc': idc,
        'parameters': [
            { 'address': 0, 'name': 'gain0', 'index': 0, 'range': (0, 15) },

            # TAC shift, neutron discriminator
            { 'address': 4, 'name': 'ndis0', 'index': 0, 'range': (0, 255) },

            # 100=no correction
            { 'address': 8, 'name': 'qwin0', 'index': 0, 'range': (0, 200) },

            { 'address': 12, 'name': 'threshold0', 'index': 0, 'range': (0, 255) },

            # offset to factory walk correction, 100=no offset
            { 'address': 16, 'name': 'walk0', 'index': 0, 'range': (50, 150) },

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
