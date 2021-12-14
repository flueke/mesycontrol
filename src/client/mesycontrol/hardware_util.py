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
__email__  = 'f.lueke@mesytec.com'

from functools import partial
import itertools
import logging

from mesycontrol.config_util import run_callables_generator
from mesycontrol.config_util import ProgressUpdate

def refresh_device_memory(devices):
    """Refreshes the memory of the given devices using device.hw.read_parameter().
    The set of parameters to (re-)read is the combination of the hardware
    profile parameters and the parameters already present in the devices memory
    cache."""

    log = logging.getLogger("refresh_device_memory")

    log.info(f"Refreshing memory of {len(devices)} devices")

    progress = ProgressUpdate(current=0, total=len(devices))
    progress.subprogress = ProgressUpdate(current=0, total=0)

    log.debug("yield initial progress")
    yield progress

    for device in devices:
        if not device.has_hw or not device.hw.is_connected():
            continue

        progress.text = "Current device: (%s, %d, %d)" % (
                device.mrc.get_display_url(), device.bus, device.address)

        log.debug("yield current progress")
        yield progress

        params    = (p.address for p in device.hw_profile.get_parameters())
        cached    = device.hw.get_cached_memory_ref().keys()
        addresses = set(itertools.chain(params, cached))

        gen = run_callables_generator(
                [partial(device.hw.read_parameter, a) for a in addresses])
        arg = None

        while True:
            try:
                log.debug(f"gen.send({arg})")
                obj = gen.send(arg)

                if isinstance(obj, ProgressUpdate):
                    progress.subprogress = obj
                    yield progress
                    arg = None
                else:
                    arg = yield obj
            except (GeneratorExit, StopIteration):
                gen.close()
                break

        yield progress.increment()
