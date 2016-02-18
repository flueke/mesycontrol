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

import logging

import hardware_controller
import hardware_model as hm
import mrc_connection

log = logging.getLogger(__name__)

def add_mrc_connection(hardware_registry, url, do_connect, connect_timeout_ms=10000):
    """Adds an MRC connection using the given url to the hardware_registry.
    If `do_connect' is True this function will start a connection attempt and
    return the corresponding Future object. Otherwise the newly added MRC will
    be in disconnected state and None is returned."""

    connection      = mrc_connection.factory(url=url)
    controller      = hardware_controller.Controller(connection)
    mrc             = hm.MRC(url)
    mrc.controller  = controller

    hardware_registry.add_mrc(mrc)

    if do_connect:
        return mrc.connect(connect_timeout_ms)

    return None

def set_default_device_extensions(device, device_registry):
    existing_exts = list()
    new_exts = list()

    p = device_registry.get_device_profile(device.idc)

    for name, ext_profile in p.get_extensions().iteritems():
        if not device.has_extension(name):
            device.set_extension(name, ext_profile['value'])
            new_exts.append((name, ext_profile['value']))
        else:
            existing_exts.append((name, ext_profile['value']))

    log.debug("set default extensions for %s: existing=%s, new=%s",
            device, existing_exts, new_exts)
