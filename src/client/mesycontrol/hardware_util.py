#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
import itertools

from config_util import run_callables_generator

def refresh_device_memory(device):
    """device: app_model.Device or specialized_device.DeviceBase instance."""

    params    = (p.address for p in device.hw_profile.get_parameters())
    cached    = device.hw.get_cached_memory_ref().iterkeys()
    addresses = set(itertools.chain(params, cached))

    gen = run_callables_generator(
            [partial(device.hw.read_parameter, a) for a in addresses])
    arg = None

    while True:
        try:
            obj = gen.send(arg)
            arg = yield obj
        except StopIteration:
            break
        except GeneratorExit:
            gen.close()
            return

    raise StopIteration()
