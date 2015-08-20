#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from mesycontrol_pb2 import *

def is_request(msg):
    return msg.Type.Name(msg.type).startswith('REQ_')

def is_response(msg):
    return msg.Type.Name(msg.type).startswith('RESP_')

def is_notification(msg):
    return msg.Type.Name(msg.type).startswith('NOTIFY_')

def is_error_response(msg):
    return msg.type == msg.RESP_ERROR
