#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

idc = 24

NUM_CHANNELS = 8

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
            { 'address': 35, 'name': 'output_source_b', 'range': (0, 1), 'default': 0 },

            # 100=no correction
            { 'address': 48, 'name': 'qwin0', 'index': 0, 'range': (0, 200) },
            ],

        'extensions': [
            ],
}
