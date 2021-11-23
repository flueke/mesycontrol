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

from google.protobuf.text_format import MessageToString
from mesycontrol.mesycontrol_pb2 import *

def is_request(msg):
    return msg.Type.Name(msg.type).startswith('REQ_')

def is_response(msg):
    return msg.Type.Name(msg.type).startswith('RESP_')

def is_notification(msg):
    return msg.Type.Name(msg.type).startswith('NOTIFY_')

def is_error_response(msg):
    return msg.type == Message.RESP_ERROR

class MessageError(RuntimeError):
    def __init__(self, message=None, request=None, text=str(), *args):
        super(MessageError, self).__init__(*args)
        self.message = message
        self.request = request
        self.text    = text

    def __str__(self):
        msg = MessageToString(self.message, as_one_line=True)
        req = MessageToString(self.request, as_one_line=True)

        return "Error(request=%s, response=%s, info=%s)" % (
                req, msg, self.text)
