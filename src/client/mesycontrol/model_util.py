#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import hardware_controller
import hardware_model as hm
import mrc_connection

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
    p = device_registry.get_device_profile(device.idc)
    for name, value in p.get_extensions().iteritems():
        if not device.has_extension(name):
            device.set_extension(name, value)
