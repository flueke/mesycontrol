#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from google.protobuf import message as proto_message
import mesycontrol_pb2 as proto

msg = proto.MesycontrolMessage()
msg.type = proto.MesycontrolMessage.REQ_READ
msg.request_read.bus = 0
msg.request_read.dev = 15
msg.request_read.par = 42
msg.request_read.mirror = False

print msg
print dir(msg)
for obj in  msg.ListFields():
    print obj

print msg.ByteSize()
print dir(msg.Type)
