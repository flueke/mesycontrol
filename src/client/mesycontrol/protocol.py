#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import struct

def deserialize_scanbus_response(type_info, data):
  ret = Message(type_info['code'])
  values = struct.unpack_from('!' + type_info['format'], data, 1)
  ret.bus = values[0]
  ret.bus_data = []
  for i in range(16):
    ret.bus_data.append((values[1+2*i], bool(values[1+2*i+1])))
  return ret

def str_scanbus_response(msg):
  ret = msg.get_type_name()
  ret += "(bus=%d: " % msg.bus

  for i in range(len(msg.bus_data)):
    idc, rc = msg.bus_data[i]
    idc = str(idc) if idc > 0 else '-'
    rc  = "ON" if rc else "OFF"
    ret += "%d:%s,%s" % (i, idc, rc)
    if i < len(msg.bus_data)-1:
      ret += ", "

  ret += ")"

  return ret

def str_error_response(msg):
  return "%s(%s)" % (msg.get_type_name(), ErrorInfo.by_code[msg.error_code]['name'])

class MessageInfo:
  info_list = [
      # requests
      { 'code': 1,
        'name': 'request_scanbus',
        'format': 'B',
        'format_args': ('bus',)
        },
      { 'code': 2,
        'name': 'request_read',
        'format': 'BBB',
        'format_args': ('bus', 'dev', 'par')
        },
      { 'code': 3,
        'name': 'request_set',
        'format': 'BBBH',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 4,
        'name': 'request_mirror_read',
        'format': 'BBB',
        'format_args': ('bus', 'dev', 'par')
        },
      { 'code': 5,
        'name': 'request_mirror_set',
        'format': 'BBBH',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 6,
        'name': 'request_rc_on',
        'format': 'BB',
        'format_args': ('bus', 'dev')
        },
      { 'code': 7,
        'name': 'request_rc_off',
        'format': 'BB',
        'format_args': ('bus', 'dev')
        },
      { 'code': 8,
        'name': 'request_reset',
        'format': 'BB',
        'format_args': ('bus', 'dev')
        },
      { 'code': 9,
        'name': 'request_copy',
        'format': 'BB',
        'format_args': ('bus', 'dev')
        },

      # responses
      { 'code': 41,
        'name': 'response_scanbus',
        'format': 'B32B',
        'deserializer': deserialize_scanbus_response,
        'str_func': str_scanbus_response
        },
      { 'code': 42,
        'name': 'response_read',
        'format': 'BBBH',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 43,
        'name': 'response_set',
        'format': 'BBBH',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 44,
        'name': 'response_mirror_read',
        'format': 'BBBH',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 45,
        'name': 'response_mirror_set',
        'format': 'BBBH',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 60,
        'name': 'response_bool',
        'format': '?',
        'format_args': ('bool_value',)
        },
      { 'code': 61,
        'name': 'response_error',
        'format': 'B',
        'format_args': ('error_code',),
        'str_func': str_error_response
        },
      ]

  by_name = {}
  by_code = {}

  for info in info_list:
    by_code[info['code']] = info
    by_name[info['name']] = info

  @staticmethod
  def get_type_names():
    return MessageInfo.by_name.keys()

class ErrorInfo:
  info_list = [
      { 'code': 1,
        'name': 'invalid_type'
        },
      { 'code': 2,
        'name': 'invalid_size'
        },
      { 'code': 3,
        'name': 'bus_out_of_range'
        },
      { 'code': 4,
        'name': 'dev_out_of_range'
        },
      { 'code': 5,
        'name': 'mrc_no_response'
        },
      { 'code': 6,
        'name': 'mrc_comm_timeout'
        },
      { 'code': 7,
        'name': 'mrc_comm_error'
        },
      { 'code': 8,
        'name': 'silenced'
        },
      { 'code': 9,
        'name': 'unknown_error'
        },
      { 'code': 10,
        'name': 'mrc_connect_error'
        },
      ]

  by_name = {}
  by_code = {}

  for info in info_list:
    by_code[info['code']] = info
    by_name[info['name']] = info

  @staticmethod
  def get_error_names():
    return ErrorInfo.by_name.keys()

class MessageError(Exception):
  pass

# TODO: override setters for bus, dev, par, value to make sure the given values
# are valid.
class Message:
  def __init__(self, type_code, **kwargs):
    try:
      type_code = int(type_code)
    except ValueError:
      # Assume a type name was given and convert it to a type code
      try:
        type_code = MessageInfo.by_name[type_code]['code']
      except KeyError:
        raise MessageError("No such message type: %s" % type_code)

    if not type_code in MessageInfo.by_code:
      raise MessageError("No such message type: %d" % type_code)

    self.type_code = type_code

    for k,v in kwargs.iteritems():
      setattr(self, k, v)

  def get_type_info(self):
    return MessageInfo.by_code[self.type_code]

  def get_type_name(self):
    return self.get_type_info()['name']

  def serialize(self):
    type_info = self.get_type_info()

    # Call the custom serializer if specified
    if type_info.has_key('serializer'):
      return type_info['serializer'](type_info, self)

    # Perform serialization using format and format_args
    data   = struct.pack('!B', self.type_code)
    values = [getattr(self, name) for name in type_info['format_args']]
    data  += struct.pack('!' + type_info['format'], *values)
    return data

  @staticmethod
  def deserialize(data):
    type_code = struct.unpack('!B', data[0])[0]
    type_info = MessageInfo.by_code[type_code]

    # Call the custom deserializer if specified
    if type_info.has_key('deserializer'):
      return type_info['deserializer'](type_info, data)

    # Perform deserialization using format and format_args
    values = struct.unpack_from('!' + type_info['format'], data, 1)

    return Message(type_code, **dict(zip(type_info['format_args'], values)))

  def __str__(self):
    type_info = self.get_type_info()

    # Call the custom string function if specified
    if type_info.has_key('str_func'):
      return type_info['str_func'](self)

    ret = type_info['name'] + "("
    n_args = len(type_info['format_args'])
    for i in range(n_args):
      name = type_info['format_args'][i]
      ret += "%s=%s" % (name, str(getattr(self, name)))
      if i < n_args-1:
        ret += ", "
    ret += ')'

    return ret;

if __name__ == "__main__":
  msg = Message('request_read', bus=1, dev=2, par=3)

  serial_data = msg.serialize()
  msg_deserialized = Message.deserialize(serial_data)

  assert msg.get_type_name() == msg_deserialized.get_type_name()
  assert msg.bus == msg_deserialized.bus
  assert msg.dev == msg_deserialized.dev
  assert msg.par == msg_deserialized.par

  print msg_deserialized

# vim:sw=2:sts=2
