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
__email__  = 'florianlueke@gmx.net'

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='mesycontrol.proto',
  package='mesycontrol.proto',
  syntax='proto3',
  serialized_pb=_b('\n\x11mesycontrol.proto\x12\x11mesycontrol.proto\"\x1d\n\x0eRequestScanbus\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\"D\n\x0bRequestRead\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\x12\x0b\n\x03\x64\x65v\x18\x02 \x01(\r\x12\x0b\n\x03par\x18\x03 \x01(\r\x12\x0e\n\x06mirror\x18\x04 \x01(\x08\"P\n\nRequestSet\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\x12\x0b\n\x03\x64\x65v\x18\x02 \x01(\r\x12\x0b\n\x03par\x18\x03 \x01(\r\x12\x0b\n\x03val\x18\x04 \x01(\x11\x12\x0e\n\x06mirror\x18\x05 \x01(\x08\"1\n\tRequestRC\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\x12\x0b\n\x03\x64\x65v\x18\x02 \x01(\r\x12\n\n\x02rc\x18\x03 \x01(\x08\"(\n\x0cRequestReset\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\x12\x0b\n\x03\x64\x65v\x18\x02 \x01(\r\"\'\n\x0bRequestCopy\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\x12\x0b\n\x03\x64\x65v\x18\x02 \x01(\r\"H\n\x10RequestReadMulti\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\x12\x0b\n\x03\x64\x65v\x18\x02 \x01(\r\x12\x0b\n\x03par\x18\x03 \x01(\r\x12\r\n\x05\x63ount\x18\x04 \x01(\r\"*\n\x19RequestAcquireWriteAccess\x12\r\n\x05\x66orce\x18\x01 \x01(\x08\"&\n\x12RequestSetSilenced\x12\x10\n\x08silenced\x18\x01 \x01(\x08\"\x97\x01\n\x13RequestSetPollItems\x12>\n\x05items\x18\x01 \x03(\x0b\x32/.mesycontrol.proto.RequestSetPollItems.PollItem\x1a@\n\x08PollItem\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\x12\x0b\n\x03\x64\x65v\x18\x02 \x01(\r\x12\x0b\n\x03par\x18\x03 \x01(\r\x12\r\n\x05\x63ount\x18\x04 \x01(\r\"\x1d\n\x0cResponseBool\x12\r\n\x05value\x18\x01 \x01(\x08\"\xb9\x02\n\rResponseError\x12\x38\n\x04type\x18\x01 \x01(\x0e\x32*.mesycontrol.proto.ResponseError.ErrorType\x12\x0c\n\x04info\x18\x02 \x01(\t\"\xdf\x01\n\tErrorType\x12\x0b\n\x07UNKNOWN\x10\x00\x12\x0f\n\x0bNO_RESPONSE\x10\x01\x12\x14\n\x10\x41\x44\x44RESS_CONFLICT\x10\x02\x12\x0e\n\nCONNECTING\x10\x03\x12\x11\n\rCONNECT_ERROR\x10\x04\x12\x0f\n\x0b\x43OM_TIMEOUT\x10\x05\x12\r\n\tCOM_ERROR\x10\x06\x12\x0c\n\x08SILENCED\x10\x07\x12\x15\n\x11PERMISSION_DENIED\x10\x08\x12\x0f\n\x0bPARSE_ERROR\x10\t\x12\x10\n\x0cINVALID_TYPE\x10\n\x12\x13\n\x0fINVALID_MESSAGE\x10\x0b\"\x97\x01\n\rScanbusResult\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\x12>\n\x07\x65ntries\x18\x02 \x03(\x0b\x32-.mesycontrol.proto.ScanbusResult.ScanbusEntry\x1a\x39\n\x0cScanbusEntry\x12\x0b\n\x03idc\x18\x01 \x01(\r\x12\n\n\x02rc\x18\x02 \x01(\x08\x12\x10\n\x08\x63onflict\x18\x03 \x01(\x08\"R\n\x0cResponseRead\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\x12\x0b\n\x03\x64\x65v\x18\x02 \x01(\r\x12\x0b\n\x03par\x18\x03 \x01(\r\x12\x0b\n\x03val\x18\x04 \x01(\x11\x12\x0e\n\x06mirror\x18\x05 \x01(\x08\"h\n\tSetResult\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\x12\x0b\n\x03\x64\x65v\x18\x02 \x01(\r\x12\x0b\n\x03par\x18\x03 \x01(\r\x12\x0b\n\x03val\x18\x04 \x01(\x11\x12\x17\n\x0frequested_value\x18\x05 \x01(\x11\x12\x0e\n\x06mirror\x18\x06 \x01(\x08\"N\n\x11ResponseReadMulti\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\x12\x0b\n\x03\x64\x65v\x18\x02 \x01(\r\x12\x0b\n\x03par\x18\x03 \x01(\r\x12\x12\n\x06values\x18\x04 \x03(\x11\x42\x02\x10\x01\"\xf8\x01\n\tMRCStatus\x12\x35\n\x04\x63ode\x18\x01 \x01(\x0e\x32\'.mesycontrol.proto.MRCStatus.StatusCode\x12\x0e\n\x06reason\x18\x02 \x01(\x05\x12\x0c\n\x04info\x18\x03 \x01(\t\x12\x0f\n\x07version\x18\x04 \x01(\t\x12\x16\n\x0ehas_read_multi\x18\x05 \x01(\x08\"m\n\nStatusCode\x12\x0b\n\x07STOPPED\x10\x00\x12\x0e\n\nCONNECTING\x10\x01\x12\x12\n\x0e\x43ONNECT_FAILED\x10\x02\x12\x10\n\x0cINITIALIZING\x10\x03\x12\x0f\n\x0bINIT_FAILED\x10\x04\x12\x0b\n\x07RUNNING\x10\x05\"<\n\x11NotifyWriteAccess\x12\x12\n\nhas_access\x18\x01 \x01(\x08\x12\x13\n\x0b\x63\x61n_acquire\x18\x02 \x01(\x08\"\"\n\x0eNotifySilenced\x12\x10\n\x08silenced\x18\x01 \x01(\x08\"\x98\x01\n\x11NotifyPolledItems\x12>\n\x05items\x18\x01 \x03(\x0b\x32/.mesycontrol.proto.NotifyPolledItems.PollResult\x1a\x43\n\nPollResult\x12\x0b\n\x03\x62us\x18\x01 \x01(\r\x12\x0b\n\x03\x64\x65v\x18\x02 \x01(\r\x12\x0b\n\x03par\x18\x03 \x01(\r\x12\x0e\n\x06values\x18\x04 \x03(\x11\"\x85\x01\n\x10NotifyClientList\x12@\n\x07\x65ntries\x18\x01 \x03(\x0b\x32/.mesycontrol.proto.NotifyClientList.ClientEntry\x1a/\n\x0b\x43lientEntry\x12\n\n\x02id\x18\x01 \x01(\t\x12\x14\n\x0cwrite_access\x18\x02 \x01(\x08\"\xdf\x0e\n\x07Message\x12-\n\x04type\x18\x01 \x01(\x0e\x32\x1f.mesycontrol.proto.Message.Type\x12:\n\x0frequest_scanbus\x18\x02 \x01(\x0b\x32!.mesycontrol.proto.RequestScanbus\x12\x34\n\x0crequest_read\x18\x03 \x01(\x0b\x32\x1e.mesycontrol.proto.RequestRead\x12\x32\n\x0brequest_set\x18\x04 \x01(\x0b\x32\x1d.mesycontrol.proto.RequestSet\x12\x30\n\nrequest_rc\x18\x05 \x01(\x0b\x32\x1c.mesycontrol.proto.RequestRC\x12\x36\n\rrequest_reset\x18\x06 \x01(\x0b\x32\x1f.mesycontrol.proto.RequestReset\x12\x34\n\x0crequest_copy\x18\x07 \x01(\x0b\x32\x1e.mesycontrol.proto.RequestCopy\x12?\n\x12request_read_multi\x18\x08 \x01(\x0b\x32#.mesycontrol.proto.RequestReadMulti\x12R\n\x1crequest_acquire_write_access\x18\t \x01(\x0b\x32,.mesycontrol.proto.RequestAcquireWriteAccess\x12\x43\n\x14request_set_silenced\x18\n \x01(\x0b\x32%.mesycontrol.proto.RequestSetSilenced\x12\x46\n\x16request_set_poll_items\x18\x0b \x01(\x0b\x32&.mesycontrol.proto.RequestSetPollItems\x12\x36\n\rresponse_bool\x18\x0c \x01(\x0b\x32\x1f.mesycontrol.proto.ResponseBool\x12\x38\n\x0eresponse_error\x18\r \x01(\x0b\x32 .mesycontrol.proto.ResponseError\x12\x36\n\rresponse_read\x18\x0e \x01(\x0b\x32\x1f.mesycontrol.proto.ResponseRead\x12\x41\n\x13response_read_multi\x18\x0f \x01(\x0b\x32$.mesycontrol.proto.ResponseReadMulti\x12\x30\n\nset_result\x18\x10 \x01(\x0b\x32\x1c.mesycontrol.proto.SetResult\x12\x38\n\x0escanbus_result\x18\x11 \x01(\x0b\x32 .mesycontrol.proto.ScanbusResult\x12\x30\n\nmrc_status\x18\x12 \x01(\x0b\x32\x1c.mesycontrol.proto.MRCStatus\x12\x41\n\x13notify_write_access\x18\x13 \x01(\x0b\x32$.mesycontrol.proto.NotifyWriteAccess\x12:\n\x0fnotify_silenced\x18\x14 \x01(\x0b\x32!.mesycontrol.proto.NotifySilenced\x12\x41\n\x13notify_polled_items\x18\x15 \x01(\x0b\x32$.mesycontrol.proto.NotifyPolledItems\x12?\n\x12notify_client_list\x18\x16 \x01(\x0b\x32#.mesycontrol.proto.NotifyClientList\"\xae\x04\n\x04Type\x12\x0f\n\x0bREQ_SCANBUS\x10\x00\x12\x0c\n\x08REQ_READ\x10\x01\x12\x0b\n\x07REQ_SET\x10\x02\x12\n\n\x06REQ_RC\x10\x03\x12\r\n\tREQ_RESET\x10\x04\x12\x0c\n\x08REQ_COPY\x10\x05\x12\x12\n\x0eREQ_READ_MULTI\x10\x06\x12\x12\n\x0eREQ_MRC_STATUS\x10\n\x12\x18\n\x14REQ_HAS_WRITE_ACCESS\x10\x0b\x12\x1c\n\x18REQ_ACQUIRE_WRITE_ACCESS\x10\x0c\x12\x1c\n\x18REQ_RELEASE_WRITE_ACCESS\x10\r\x12\x13\n\x0fREQ_IS_SILENCED\x10\x0e\x12\x14\n\x10REQ_SET_SILENCED\x10\x0f\x12\x16\n\x12REQ_SET_POLL_ITEMS\x10\x10\x12\r\n\tRESP_BOOL\x10\x14\x12\x0e\n\nRESP_ERROR\x10\x15\x12\x10\n\x0cRESP_SCANBUS\x10\x16\x12\r\n\tRESP_READ\x10\x17\x12\x0c\n\x08RESP_SET\x10\x18\x12\x13\n\x0fRESP_READ_MULTI\x10\x19\x12\x13\n\x0fRESP_MRC_STATUS\x10\x1a\x12\x12\n\x0eNOTIFY_SCANBUS\x10\x1f\x12\x15\n\x11NOTIFY_MRC_STATUS\x10 \x12\x17\n\x13NOTIFY_WRITE_ACCESS\x10!\x12\x13\n\x0fNOTIFY_SILENCED\x10\"\x12\x0e\n\nNOTIFY_SET\x10#\x12\x17\n\x13NOTIFY_POLLED_ITEMS\x10$\x12\x16\n\x12NOTIFY_CLIENT_LIST\x10%b\x06proto3')
)
_sym_db.RegisterFileDescriptor(DESCRIPTOR)



_RESPONSEERROR_ERRORTYPE = _descriptor.EnumDescriptor(
  name='ErrorType',
  full_name='mesycontrol.proto.ResponseError.ErrorType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='UNKNOWN', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='NO_RESPONSE', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ADDRESS_CONFLICT', index=2, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CONNECTING', index=3, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CONNECT_ERROR', index=4, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='COM_TIMEOUT', index=5, number=5,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='COM_ERROR', index=6, number=6,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='SILENCED', index=7, number=7,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='PERMISSION_DENIED', index=8, number=8,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='PARSE_ERROR', index=9, number=9,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='INVALID_TYPE', index=10, number=10,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='INVALID_MESSAGE', index=11, number=11,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=791,
  serialized_end=1014,
)
_sym_db.RegisterEnumDescriptor(_RESPONSEERROR_ERRORTYPE)

_MRCSTATUS_STATUSCODE = _descriptor.EnumDescriptor(
  name='StatusCode',
  full_name='mesycontrol.proto.MRCStatus.StatusCode',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='STOPPED', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CONNECTING', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='CONNECT_FAILED', index=2, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='INITIALIZING', index=3, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='INIT_FAILED', index=4, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RUNNING', index=5, number=5,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=1580,
  serialized_end=1689,
)
_sym_db.RegisterEnumDescriptor(_MRCSTATUS_STATUSCODE)

_MESSAGE_TYPE = _descriptor.EnumDescriptor(
  name='Type',
  full_name='mesycontrol.proto.Message.Type',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='REQ_SCANBUS', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_READ', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_SET', index=2, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_RC', index=3, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_RESET', index=4, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_COPY', index=5, number=5,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_READ_MULTI', index=6, number=6,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_MRC_STATUS', index=7, number=10,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_HAS_WRITE_ACCESS', index=8, number=11,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_ACQUIRE_WRITE_ACCESS', index=9, number=12,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_RELEASE_WRITE_ACCESS', index=10, number=13,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_IS_SILENCED', index=11, number=14,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_SET_SILENCED', index=12, number=15,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REQ_SET_POLL_ITEMS', index=13, number=16,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RESP_BOOL', index=14, number=20,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RESP_ERROR', index=15, number=21,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RESP_SCANBUS', index=16, number=22,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RESP_READ', index=17, number=23,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RESP_SET', index=18, number=24,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RESP_READ_MULTI', index=19, number=25,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RESP_MRC_STATUS', index=20, number=26,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='NOTIFY_SCANBUS', index=21, number=31,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='NOTIFY_MRC_STATUS', index=22, number=32,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='NOTIFY_WRITE_ACCESS', index=23, number=33,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='NOTIFY_SILENCED', index=24, number=34,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='NOTIFY_SET', index=25, number=35,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='NOTIFY_POLLED_ITEMS', index=26, number=36,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='NOTIFY_CLIENT_LIST', index=27, number=37,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=3410,
  serialized_end=3968,
)
_sym_db.RegisterEnumDescriptor(_MESSAGE_TYPE)


_REQUESTSCANBUS = _descriptor.Descriptor(
  name='RequestScanbus',
  full_name='mesycontrol.proto.RequestScanbus',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.RequestScanbus.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=40,
  serialized_end=69,
)


_REQUESTREAD = _descriptor.Descriptor(
  name='RequestRead',
  full_name='mesycontrol.proto.RequestRead',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.RequestRead.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='dev', full_name='mesycontrol.proto.RequestRead.dev', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='par', full_name='mesycontrol.proto.RequestRead.par', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='mirror', full_name='mesycontrol.proto.RequestRead.mirror', index=3,
      number=4, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=71,
  serialized_end=139,
)


_REQUESTSET = _descriptor.Descriptor(
  name='RequestSet',
  full_name='mesycontrol.proto.RequestSet',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.RequestSet.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='dev', full_name='mesycontrol.proto.RequestSet.dev', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='par', full_name='mesycontrol.proto.RequestSet.par', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='val', full_name='mesycontrol.proto.RequestSet.val', index=3,
      number=4, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='mirror', full_name='mesycontrol.proto.RequestSet.mirror', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=141,
  serialized_end=221,
)


_REQUESTRC = _descriptor.Descriptor(
  name='RequestRC',
  full_name='mesycontrol.proto.RequestRC',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.RequestRC.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='dev', full_name='mesycontrol.proto.RequestRC.dev', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='rc', full_name='mesycontrol.proto.RequestRC.rc', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=223,
  serialized_end=272,
)


_REQUESTRESET = _descriptor.Descriptor(
  name='RequestReset',
  full_name='mesycontrol.proto.RequestReset',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.RequestReset.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='dev', full_name='mesycontrol.proto.RequestReset.dev', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=274,
  serialized_end=314,
)


_REQUESTCOPY = _descriptor.Descriptor(
  name='RequestCopy',
  full_name='mesycontrol.proto.RequestCopy',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.RequestCopy.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='dev', full_name='mesycontrol.proto.RequestCopy.dev', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=316,
  serialized_end=355,
)


_REQUESTREADMULTI = _descriptor.Descriptor(
  name='RequestReadMulti',
  full_name='mesycontrol.proto.RequestReadMulti',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.RequestReadMulti.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='dev', full_name='mesycontrol.proto.RequestReadMulti.dev', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='par', full_name='mesycontrol.proto.RequestReadMulti.par', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='count', full_name='mesycontrol.proto.RequestReadMulti.count', index=3,
      number=4, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=357,
  serialized_end=429,
)


_REQUESTACQUIREWRITEACCESS = _descriptor.Descriptor(
  name='RequestAcquireWriteAccess',
  full_name='mesycontrol.proto.RequestAcquireWriteAccess',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='force', full_name='mesycontrol.proto.RequestAcquireWriteAccess.force', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=431,
  serialized_end=473,
)


_REQUESTSETSILENCED = _descriptor.Descriptor(
  name='RequestSetSilenced',
  full_name='mesycontrol.proto.RequestSetSilenced',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='silenced', full_name='mesycontrol.proto.RequestSetSilenced.silenced', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=475,
  serialized_end=513,
)


_REQUESTSETPOLLITEMS_POLLITEM = _descriptor.Descriptor(
  name='PollItem',
  full_name='mesycontrol.proto.RequestSetPollItems.PollItem',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.RequestSetPollItems.PollItem.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='dev', full_name='mesycontrol.proto.RequestSetPollItems.PollItem.dev', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='par', full_name='mesycontrol.proto.RequestSetPollItems.PollItem.par', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='count', full_name='mesycontrol.proto.RequestSetPollItems.PollItem.count', index=3,
      number=4, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=603,
  serialized_end=667,
)

_REQUESTSETPOLLITEMS = _descriptor.Descriptor(
  name='RequestSetPollItems',
  full_name='mesycontrol.proto.RequestSetPollItems',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='items', full_name='mesycontrol.proto.RequestSetPollItems.items', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_REQUESTSETPOLLITEMS_POLLITEM, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=516,
  serialized_end=667,
)


_RESPONSEBOOL = _descriptor.Descriptor(
  name='ResponseBool',
  full_name='mesycontrol.proto.ResponseBool',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='value', full_name='mesycontrol.proto.ResponseBool.value', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=669,
  serialized_end=698,
)


_RESPONSEERROR = _descriptor.Descriptor(
  name='ResponseError',
  full_name='mesycontrol.proto.ResponseError',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='type', full_name='mesycontrol.proto.ResponseError.type', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='info', full_name='mesycontrol.proto.ResponseError.info', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _RESPONSEERROR_ERRORTYPE,
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=701,
  serialized_end=1014,
)


_SCANBUSRESULT_SCANBUSENTRY = _descriptor.Descriptor(
  name='ScanbusEntry',
  full_name='mesycontrol.proto.ScanbusResult.ScanbusEntry',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='idc', full_name='mesycontrol.proto.ScanbusResult.ScanbusEntry.idc', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='rc', full_name='mesycontrol.proto.ScanbusResult.ScanbusEntry.rc', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='conflict', full_name='mesycontrol.proto.ScanbusResult.ScanbusEntry.conflict', index=2,
      number=3, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1111,
  serialized_end=1168,
)

_SCANBUSRESULT = _descriptor.Descriptor(
  name='ScanbusResult',
  full_name='mesycontrol.proto.ScanbusResult',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.ScanbusResult.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='entries', full_name='mesycontrol.proto.ScanbusResult.entries', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_SCANBUSRESULT_SCANBUSENTRY, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1017,
  serialized_end=1168,
)


_RESPONSEREAD = _descriptor.Descriptor(
  name='ResponseRead',
  full_name='mesycontrol.proto.ResponseRead',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.ResponseRead.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='dev', full_name='mesycontrol.proto.ResponseRead.dev', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='par', full_name='mesycontrol.proto.ResponseRead.par', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='val', full_name='mesycontrol.proto.ResponseRead.val', index=3,
      number=4, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='mirror', full_name='mesycontrol.proto.ResponseRead.mirror', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1170,
  serialized_end=1252,
)


_SETRESULT = _descriptor.Descriptor(
  name='SetResult',
  full_name='mesycontrol.proto.SetResult',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.SetResult.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='dev', full_name='mesycontrol.proto.SetResult.dev', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='par', full_name='mesycontrol.proto.SetResult.par', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='val', full_name='mesycontrol.proto.SetResult.val', index=3,
      number=4, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='requested_value', full_name='mesycontrol.proto.SetResult.requested_value', index=4,
      number=5, type=17, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='mirror', full_name='mesycontrol.proto.SetResult.mirror', index=5,
      number=6, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1254,
  serialized_end=1358,
)


_RESPONSEREADMULTI = _descriptor.Descriptor(
  name='ResponseReadMulti',
  full_name='mesycontrol.proto.ResponseReadMulti',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.ResponseReadMulti.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='dev', full_name='mesycontrol.proto.ResponseReadMulti.dev', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='par', full_name='mesycontrol.proto.ResponseReadMulti.par', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='values', full_name='mesycontrol.proto.ResponseReadMulti.values', index=3,
      number=4, type=17, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=_descriptor._ParseOptions(descriptor_pb2.FieldOptions(), _b('\020\001'))),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1360,
  serialized_end=1438,
)


_MRCSTATUS = _descriptor.Descriptor(
  name='MRCStatus',
  full_name='mesycontrol.proto.MRCStatus',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='code', full_name='mesycontrol.proto.MRCStatus.code', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='reason', full_name='mesycontrol.proto.MRCStatus.reason', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='info', full_name='mesycontrol.proto.MRCStatus.info', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='version', full_name='mesycontrol.proto.MRCStatus.version', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='has_read_multi', full_name='mesycontrol.proto.MRCStatus.has_read_multi', index=4,
      number=5, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _MRCSTATUS_STATUSCODE,
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1441,
  serialized_end=1689,
)


_NOTIFYWRITEACCESS = _descriptor.Descriptor(
  name='NotifyWriteAccess',
  full_name='mesycontrol.proto.NotifyWriteAccess',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='has_access', full_name='mesycontrol.proto.NotifyWriteAccess.has_access', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='can_acquire', full_name='mesycontrol.proto.NotifyWriteAccess.can_acquire', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1691,
  serialized_end=1751,
)


_NOTIFYSILENCED = _descriptor.Descriptor(
  name='NotifySilenced',
  full_name='mesycontrol.proto.NotifySilenced',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='silenced', full_name='mesycontrol.proto.NotifySilenced.silenced', index=0,
      number=1, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1753,
  serialized_end=1787,
)


_NOTIFYPOLLEDITEMS_POLLRESULT = _descriptor.Descriptor(
  name='PollResult',
  full_name='mesycontrol.proto.NotifyPolledItems.PollResult',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='bus', full_name='mesycontrol.proto.NotifyPolledItems.PollResult.bus', index=0,
      number=1, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='dev', full_name='mesycontrol.proto.NotifyPolledItems.PollResult.dev', index=1,
      number=2, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='par', full_name='mesycontrol.proto.NotifyPolledItems.PollResult.par', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='values', full_name='mesycontrol.proto.NotifyPolledItems.PollResult.values', index=3,
      number=4, type=17, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1875,
  serialized_end=1942,
)

_NOTIFYPOLLEDITEMS = _descriptor.Descriptor(
  name='NotifyPolledItems',
  full_name='mesycontrol.proto.NotifyPolledItems',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='items', full_name='mesycontrol.proto.NotifyPolledItems.items', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_NOTIFYPOLLEDITEMS_POLLRESULT, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1790,
  serialized_end=1942,
)


_NOTIFYCLIENTLIST_CLIENTENTRY = _descriptor.Descriptor(
  name='ClientEntry',
  full_name='mesycontrol.proto.NotifyClientList.ClientEntry',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='id', full_name='mesycontrol.proto.NotifyClientList.ClientEntry.id', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='write_access', full_name='mesycontrol.proto.NotifyClientList.ClientEntry.write_access', index=1,
      number=2, type=8, cpp_type=7, label=1,
      has_default_value=False, default_value=False,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=2031,
  serialized_end=2078,
)

_NOTIFYCLIENTLIST = _descriptor.Descriptor(
  name='NotifyClientList',
  full_name='mesycontrol.proto.NotifyClientList',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='entries', full_name='mesycontrol.proto.NotifyClientList.entries', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_NOTIFYCLIENTLIST_CLIENTENTRY, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1945,
  serialized_end=2078,
)


_MESSAGE = _descriptor.Descriptor(
  name='Message',
  full_name='mesycontrol.proto.Message',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='type', full_name='mesycontrol.proto.Message.type', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='request_scanbus', full_name='mesycontrol.proto.Message.request_scanbus', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='request_read', full_name='mesycontrol.proto.Message.request_read', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='request_set', full_name='mesycontrol.proto.Message.request_set', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='request_rc', full_name='mesycontrol.proto.Message.request_rc', index=4,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='request_reset', full_name='mesycontrol.proto.Message.request_reset', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='request_copy', full_name='mesycontrol.proto.Message.request_copy', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='request_read_multi', full_name='mesycontrol.proto.Message.request_read_multi', index=7,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='request_acquire_write_access', full_name='mesycontrol.proto.Message.request_acquire_write_access', index=8,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='request_set_silenced', full_name='mesycontrol.proto.Message.request_set_silenced', index=9,
      number=10, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='request_set_poll_items', full_name='mesycontrol.proto.Message.request_set_poll_items', index=10,
      number=11, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='response_bool', full_name='mesycontrol.proto.Message.response_bool', index=11,
      number=12, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='response_error', full_name='mesycontrol.proto.Message.response_error', index=12,
      number=13, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='response_read', full_name='mesycontrol.proto.Message.response_read', index=13,
      number=14, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='response_read_multi', full_name='mesycontrol.proto.Message.response_read_multi', index=14,
      number=15, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='set_result', full_name='mesycontrol.proto.Message.set_result', index=15,
      number=16, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='scanbus_result', full_name='mesycontrol.proto.Message.scanbus_result', index=16,
      number=17, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='mrc_status', full_name='mesycontrol.proto.Message.mrc_status', index=17,
      number=18, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='notify_write_access', full_name='mesycontrol.proto.Message.notify_write_access', index=18,
      number=19, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='notify_silenced', full_name='mesycontrol.proto.Message.notify_silenced', index=19,
      number=20, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='notify_polled_items', full_name='mesycontrol.proto.Message.notify_polled_items', index=20,
      number=21, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='notify_client_list', full_name='mesycontrol.proto.Message.notify_client_list', index=21,
      number=22, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _MESSAGE_TYPE,
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=2081,
  serialized_end=3968,
)

_REQUESTSETPOLLITEMS_POLLITEM.containing_type = _REQUESTSETPOLLITEMS
_REQUESTSETPOLLITEMS.fields_by_name['items'].message_type = _REQUESTSETPOLLITEMS_POLLITEM
_RESPONSEERROR.fields_by_name['type'].enum_type = _RESPONSEERROR_ERRORTYPE
_RESPONSEERROR_ERRORTYPE.containing_type = _RESPONSEERROR
_SCANBUSRESULT_SCANBUSENTRY.containing_type = _SCANBUSRESULT
_SCANBUSRESULT.fields_by_name['entries'].message_type = _SCANBUSRESULT_SCANBUSENTRY
_MRCSTATUS.fields_by_name['code'].enum_type = _MRCSTATUS_STATUSCODE
_MRCSTATUS_STATUSCODE.containing_type = _MRCSTATUS
_NOTIFYPOLLEDITEMS_POLLRESULT.containing_type = _NOTIFYPOLLEDITEMS
_NOTIFYPOLLEDITEMS.fields_by_name['items'].message_type = _NOTIFYPOLLEDITEMS_POLLRESULT
_NOTIFYCLIENTLIST_CLIENTENTRY.containing_type = _NOTIFYCLIENTLIST
_NOTIFYCLIENTLIST.fields_by_name['entries'].message_type = _NOTIFYCLIENTLIST_CLIENTENTRY
_MESSAGE.fields_by_name['type'].enum_type = _MESSAGE_TYPE
_MESSAGE.fields_by_name['request_scanbus'].message_type = _REQUESTSCANBUS
_MESSAGE.fields_by_name['request_read'].message_type = _REQUESTREAD
_MESSAGE.fields_by_name['request_set'].message_type = _REQUESTSET
_MESSAGE.fields_by_name['request_rc'].message_type = _REQUESTRC
_MESSAGE.fields_by_name['request_reset'].message_type = _REQUESTRESET
_MESSAGE.fields_by_name['request_copy'].message_type = _REQUESTCOPY
_MESSAGE.fields_by_name['request_read_multi'].message_type = _REQUESTREADMULTI
_MESSAGE.fields_by_name['request_acquire_write_access'].message_type = _REQUESTACQUIREWRITEACCESS
_MESSAGE.fields_by_name['request_set_silenced'].message_type = _REQUESTSETSILENCED
_MESSAGE.fields_by_name['request_set_poll_items'].message_type = _REQUESTSETPOLLITEMS
_MESSAGE.fields_by_name['response_bool'].message_type = _RESPONSEBOOL
_MESSAGE.fields_by_name['response_error'].message_type = _RESPONSEERROR
_MESSAGE.fields_by_name['response_read'].message_type = _RESPONSEREAD
_MESSAGE.fields_by_name['response_read_multi'].message_type = _RESPONSEREADMULTI
_MESSAGE.fields_by_name['set_result'].message_type = _SETRESULT
_MESSAGE.fields_by_name['scanbus_result'].message_type = _SCANBUSRESULT
_MESSAGE.fields_by_name['mrc_status'].message_type = _MRCSTATUS
_MESSAGE.fields_by_name['notify_write_access'].message_type = _NOTIFYWRITEACCESS
_MESSAGE.fields_by_name['notify_silenced'].message_type = _NOTIFYSILENCED
_MESSAGE.fields_by_name['notify_polled_items'].message_type = _NOTIFYPOLLEDITEMS
_MESSAGE.fields_by_name['notify_client_list'].message_type = _NOTIFYCLIENTLIST
_MESSAGE_TYPE.containing_type = _MESSAGE
DESCRIPTOR.message_types_by_name['RequestScanbus'] = _REQUESTSCANBUS
DESCRIPTOR.message_types_by_name['RequestRead'] = _REQUESTREAD
DESCRIPTOR.message_types_by_name['RequestSet'] = _REQUESTSET
DESCRIPTOR.message_types_by_name['RequestRC'] = _REQUESTRC
DESCRIPTOR.message_types_by_name['RequestReset'] = _REQUESTRESET
DESCRIPTOR.message_types_by_name['RequestCopy'] = _REQUESTCOPY
DESCRIPTOR.message_types_by_name['RequestReadMulti'] = _REQUESTREADMULTI
DESCRIPTOR.message_types_by_name['RequestAcquireWriteAccess'] = _REQUESTACQUIREWRITEACCESS
DESCRIPTOR.message_types_by_name['RequestSetSilenced'] = _REQUESTSETSILENCED
DESCRIPTOR.message_types_by_name['RequestSetPollItems'] = _REQUESTSETPOLLITEMS
DESCRIPTOR.message_types_by_name['ResponseBool'] = _RESPONSEBOOL
DESCRIPTOR.message_types_by_name['ResponseError'] = _RESPONSEERROR
DESCRIPTOR.message_types_by_name['ScanbusResult'] = _SCANBUSRESULT
DESCRIPTOR.message_types_by_name['ResponseRead'] = _RESPONSEREAD
DESCRIPTOR.message_types_by_name['SetResult'] = _SETRESULT
DESCRIPTOR.message_types_by_name['ResponseReadMulti'] = _RESPONSEREADMULTI
DESCRIPTOR.message_types_by_name['MRCStatus'] = _MRCSTATUS
DESCRIPTOR.message_types_by_name['NotifyWriteAccess'] = _NOTIFYWRITEACCESS
DESCRIPTOR.message_types_by_name['NotifySilenced'] = _NOTIFYSILENCED
DESCRIPTOR.message_types_by_name['NotifyPolledItems'] = _NOTIFYPOLLEDITEMS
DESCRIPTOR.message_types_by_name['NotifyClientList'] = _NOTIFYCLIENTLIST
DESCRIPTOR.message_types_by_name['Message'] = _MESSAGE

RequestScanbus = _reflection.GeneratedProtocolMessageType('RequestScanbus', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTSCANBUS,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.RequestScanbus)
  ))
_sym_db.RegisterMessage(RequestScanbus)

RequestRead = _reflection.GeneratedProtocolMessageType('RequestRead', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTREAD,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.RequestRead)
  ))
_sym_db.RegisterMessage(RequestRead)

RequestSet = _reflection.GeneratedProtocolMessageType('RequestSet', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTSET,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.RequestSet)
  ))
_sym_db.RegisterMessage(RequestSet)

RequestRC = _reflection.GeneratedProtocolMessageType('RequestRC', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTRC,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.RequestRC)
  ))
_sym_db.RegisterMessage(RequestRC)

RequestReset = _reflection.GeneratedProtocolMessageType('RequestReset', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTRESET,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.RequestReset)
  ))
_sym_db.RegisterMessage(RequestReset)

RequestCopy = _reflection.GeneratedProtocolMessageType('RequestCopy', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTCOPY,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.RequestCopy)
  ))
_sym_db.RegisterMessage(RequestCopy)

RequestReadMulti = _reflection.GeneratedProtocolMessageType('RequestReadMulti', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTREADMULTI,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.RequestReadMulti)
  ))
_sym_db.RegisterMessage(RequestReadMulti)

RequestAcquireWriteAccess = _reflection.GeneratedProtocolMessageType('RequestAcquireWriteAccess', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTACQUIREWRITEACCESS,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.RequestAcquireWriteAccess)
  ))
_sym_db.RegisterMessage(RequestAcquireWriteAccess)

RequestSetSilenced = _reflection.GeneratedProtocolMessageType('RequestSetSilenced', (_message.Message,), dict(
  DESCRIPTOR = _REQUESTSETSILENCED,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.RequestSetSilenced)
  ))
_sym_db.RegisterMessage(RequestSetSilenced)

RequestSetPollItems = _reflection.GeneratedProtocolMessageType('RequestSetPollItems', (_message.Message,), dict(

  PollItem = _reflection.GeneratedProtocolMessageType('PollItem', (_message.Message,), dict(
    DESCRIPTOR = _REQUESTSETPOLLITEMS_POLLITEM,
    __module__ = 'mesycontrol_pb2'
    # @@protoc_insertion_point(class_scope:mesycontrol.proto.RequestSetPollItems.PollItem)
    ))
  ,
  DESCRIPTOR = _REQUESTSETPOLLITEMS,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.RequestSetPollItems)
  ))
_sym_db.RegisterMessage(RequestSetPollItems)
_sym_db.RegisterMessage(RequestSetPollItems.PollItem)

ResponseBool = _reflection.GeneratedProtocolMessageType('ResponseBool', (_message.Message,), dict(
  DESCRIPTOR = _RESPONSEBOOL,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.ResponseBool)
  ))
_sym_db.RegisterMessage(ResponseBool)

ResponseError = _reflection.GeneratedProtocolMessageType('ResponseError', (_message.Message,), dict(
  DESCRIPTOR = _RESPONSEERROR,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.ResponseError)
  ))
_sym_db.RegisterMessage(ResponseError)

ScanbusResult = _reflection.GeneratedProtocolMessageType('ScanbusResult', (_message.Message,), dict(

  ScanbusEntry = _reflection.GeneratedProtocolMessageType('ScanbusEntry', (_message.Message,), dict(
    DESCRIPTOR = _SCANBUSRESULT_SCANBUSENTRY,
    __module__ = 'mesycontrol_pb2'
    # @@protoc_insertion_point(class_scope:mesycontrol.proto.ScanbusResult.ScanbusEntry)
    ))
  ,
  DESCRIPTOR = _SCANBUSRESULT,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.ScanbusResult)
  ))
_sym_db.RegisterMessage(ScanbusResult)
_sym_db.RegisterMessage(ScanbusResult.ScanbusEntry)

ResponseRead = _reflection.GeneratedProtocolMessageType('ResponseRead', (_message.Message,), dict(
  DESCRIPTOR = _RESPONSEREAD,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.ResponseRead)
  ))
_sym_db.RegisterMessage(ResponseRead)

SetResult = _reflection.GeneratedProtocolMessageType('SetResult', (_message.Message,), dict(
  DESCRIPTOR = _SETRESULT,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.SetResult)
  ))
_sym_db.RegisterMessage(SetResult)

ResponseReadMulti = _reflection.GeneratedProtocolMessageType('ResponseReadMulti', (_message.Message,), dict(
  DESCRIPTOR = _RESPONSEREADMULTI,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.ResponseReadMulti)
  ))
_sym_db.RegisterMessage(ResponseReadMulti)

MRCStatus = _reflection.GeneratedProtocolMessageType('MRCStatus', (_message.Message,), dict(
  DESCRIPTOR = _MRCSTATUS,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.MRCStatus)
  ))
_sym_db.RegisterMessage(MRCStatus)

NotifyWriteAccess = _reflection.GeneratedProtocolMessageType('NotifyWriteAccess', (_message.Message,), dict(
  DESCRIPTOR = _NOTIFYWRITEACCESS,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.NotifyWriteAccess)
  ))
_sym_db.RegisterMessage(NotifyWriteAccess)

NotifySilenced = _reflection.GeneratedProtocolMessageType('NotifySilenced', (_message.Message,), dict(
  DESCRIPTOR = _NOTIFYSILENCED,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.NotifySilenced)
  ))
_sym_db.RegisterMessage(NotifySilenced)

NotifyPolledItems = _reflection.GeneratedProtocolMessageType('NotifyPolledItems', (_message.Message,), dict(

  PollResult = _reflection.GeneratedProtocolMessageType('PollResult', (_message.Message,), dict(
    DESCRIPTOR = _NOTIFYPOLLEDITEMS_POLLRESULT,
    __module__ = 'mesycontrol_pb2'
    # @@protoc_insertion_point(class_scope:mesycontrol.proto.NotifyPolledItems.PollResult)
    ))
  ,
  DESCRIPTOR = _NOTIFYPOLLEDITEMS,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.NotifyPolledItems)
  ))
_sym_db.RegisterMessage(NotifyPolledItems)
_sym_db.RegisterMessage(NotifyPolledItems.PollResult)

NotifyClientList = _reflection.GeneratedProtocolMessageType('NotifyClientList', (_message.Message,), dict(

  ClientEntry = _reflection.GeneratedProtocolMessageType('ClientEntry', (_message.Message,), dict(
    DESCRIPTOR = _NOTIFYCLIENTLIST_CLIENTENTRY,
    __module__ = 'mesycontrol_pb2'
    # @@protoc_insertion_point(class_scope:mesycontrol.proto.NotifyClientList.ClientEntry)
    ))
  ,
  DESCRIPTOR = _NOTIFYCLIENTLIST,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.NotifyClientList)
  ))
_sym_db.RegisterMessage(NotifyClientList)
_sym_db.RegisterMessage(NotifyClientList.ClientEntry)

Message = _reflection.GeneratedProtocolMessageType('Message', (_message.Message,), dict(
  DESCRIPTOR = _MESSAGE,
  __module__ = 'mesycontrol_pb2'
  # @@protoc_insertion_point(class_scope:mesycontrol.proto.Message)
  ))
_sym_db.RegisterMessage(Message)


_RESPONSEREADMULTI.fields_by_name['values'].has_options = True
_RESPONSEREADMULTI.fields_by_name['values']._options = _descriptor._ParseOptions(descriptor_pb2.FieldOptions(), _b('\020\001'))
# @@protoc_insertion_point(module_scope)
