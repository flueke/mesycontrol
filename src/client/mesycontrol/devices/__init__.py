#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

device_modules = [
    'mcfd16',
    'mhv4' ,
    'mscf16_ng',
    'stm16',
    ]

profile_modules = [
    'device_profile_mcfd16',
    'device_profile_mhv4',
    'device_profile_mscf16',
    'device_profile_stm16',
    ]

__all__ = device_modules + profile_modules
