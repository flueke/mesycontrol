#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from google.protobuf.text_format import MessageToString
from mesycontrol_pb2 import *

def is_request(msg):
    return msg.Type.Name(msg.type).startswith('REQ_')

def is_response(msg):
    return msg.Type.Name(msg.type).startswith('RESP_')

def is_notification(msg):
    return msg.Type.Name(msg.type).startswith('NOTIFY_')

def is_error_response(msg):
    return msg.type == Message.RESP_ERROR

class MessageError(RuntimeError):
    def __init__(self, message=None, request=None, text=None, *args):
        super(MessageError, self).__init__(*args)
        self.message = message
        self.request = request
        self.text    = text

    def __str__(self):
        msg = MessageToString(self.message, as_one_line=True)
        req = MessageToString(self.request, as_one_line=True)

        return "Error(request=%s, response=%s, info=%s)" % (
                req, msg, self.text)
