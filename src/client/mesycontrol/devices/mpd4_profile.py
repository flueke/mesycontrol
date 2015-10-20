#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

idc = 21

NUM_CHANNELS = 4

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
