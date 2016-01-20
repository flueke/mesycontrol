#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
import itertools

from config_util import run_callables_generator
from config_util import ProgressUpdate

def refresh_device_memory(devices):
    """Refreshes the memory of the given devices using device.hw.read_parameter().
    The set of parameters to (re-)read is the combination of the hardware
    profile parameters and the parameters already present in the devices memory
    cache."""

    progress = ProgressUpdate(current=0, total=len(devices))
    progress.subprogress = ProgressUpdate(current=0, total=0)

    yield progress

    for device in devices:
        if not device.has_hw or not device.hw.is_connected():
            continue

        progress.text = "Current device: (%s, %d, %d)" % (
                device.mrc.get_display_url(), device.bus, device.address)

        yield progress

        params    = (p.address for p in device.hw_profile.get_parameters())
        cached    = device.hw.get_cached_memory_ref().iterkeys()
        addresses = set(itertools.chain(params, cached))

        gen = run_callables_generator(
                [partial(device.hw.read_parameter, a) for a in addresses])
        arg = None

        while True:
            try:
                obj = gen.send(arg)

                if isinstance(obj, ProgressUpdate):
                    progress.subprogress = obj
                    yield progress
                    arg = None
                else:
                    arg = yield obj
            except StopIteration:
                break
            except GeneratorExit:
                gen.close()
                return

        yield progress.increment()

    raise StopIteration()
