#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

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

