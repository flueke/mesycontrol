#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import struct
from mesycontrol.protocol import Message
from mesycontrol.protocol import MessageInfo

def test_make_read_multi_request():
    r = Message('request_read_multi', bus=0, dev=13, par=100, n_params=155)

    assert r.get_type_name() == 'request_read_multi'
    assert r.bus == 0
    assert r.dev == 13
    assert r.par == 100
    assert r.n_params == 155

def test_deserialize_read_multi_response():
    # create a buffer containing 20 values starting at param=10 for bus=1, dev=13
    packed = struct.pack('!BBBB20i', MessageInfo.by_name['response_read_multi']['code'],
            1, 13, 10, *[i for i in range(20)])

    msg    = Message.deserialize(packed)

    assert msg.get_type_name() == 'response_read_multi'
    assert msg.bus == 1
    assert msg.dev == 13
    assert msg.par == 10
    assert len(msg.values) == 20
    assert msg.values == dict([(i+10, i) for i in range(20)])
