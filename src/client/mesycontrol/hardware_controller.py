#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import protocol
import util

class Controller(object):
    def __init__(self):
        self.mrc = None
        self.connection = None
        self.log        = util.make_logging_source_adapter(__name__, self)

    def read_parameter(self, bus, device, address):
        def response_received(f):
            try:
                self.mrc.get_device(bus, device).set_cached_parameter(f.result().value)
            except Exception:
                self.log.error(exc_info=True)

        m = protocol.Message('request_read', bus=bus, dev=device, par=address)
        return self.connection.queue_request(m).add_done_callback(response_received)

    def set_parameter(self, bus, device, address, value):
        def response_received(f):
            try:
                self.mrc.get_device(bus, device).set_cached_parameter(f.result().value)
            except Exception:
                self.log.error(exc_info=True)

        m = protocol.Message('request_set', bus=bus, dev=device, par=address, val=value)
        return self.connection.queue_request(m).add_done_callback(response_received)

    def scanbus(self, bus, response_handler=None):
        m = protocol.Message('request_scanbus', bus=bus)
