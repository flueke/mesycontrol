#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import struct

def deserialize_scanbus_response(type_info, data):
  ret = ScanbusResponse(type_info['code'])
  values = struct.unpack_from('!' + type_info['format'], data, 1)
  ret.bus = values[0]
  ret.bus_data = []
  for i in range(16):
    ret.bus_data.append((values[1+2*i], values[1+2*i+1]))
  return ret

def str_scanbus_response(msg):
  ret = msg.get_type_name()
  ret += "(bus=%d: " % msg.bus

  for i, data in enumerate(msg.bus_data):
    idc, rc = data
    
    idc = str(idc) if idc > 0 else '-'
    if rc in (0, 1):
      rc  = "ON" if rc else "OFF"
    else:
      rc  = 'C!'
    ret += "%d:%s,%s" % (i, idc, rc)
    if i < len(msg.bus_data)-1:
      ret += ", "

  ret += ")"

  return ret

def str_error_response(msg):
  return "%s(%s)" % (msg.get_type_name(), ErrorInfo.by_code[msg.error_code]['name'])

class MessageError(Exception):
  pass

class InvalidMessageType(MessageError):
  def __init__(self, type_code):
    super(InvalidMessageType, self).__init__()
    self.type_code = type_code

  def __str__(self):
    return "No such message type '%s'" % str(self.type_code)

class MessageInfo:
  info_list = [
      # Requests
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
        'format': 'BBBi',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 4,
        'name': 'request_mirror_read',
        'format': 'BBB',
        'format_args': ('bus', 'dev', 'par')
        },
      { 'code': 5,
        'name': 'request_mirror_set',
        'format': 'BBBi',
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


      { 'code': 20,
        'name': 'request_has_write_access',
        'format': '',
        'format_args': ()
        },

      { 'code': 21,
        'name': 'request_acquire_write_access',
        'format': '',
        'format_args': ()
        },

      { 'code': 22,
        'name': 'request_release_write_access',
        'format': '',
        'format_args': ()
        },

      { 'code': 23,
        'name': 'request_in_silent_mode',
        'format': '',
        'format_args': ()
        },

      { 'code': 24,
        'name': 'request_set_silent_mode',
        'format': '?',
        'format_args': ('bool_value',)
        },

      { 'code': 25,
        'name': 'request_force_write_access',
        'format': '',
        'format_args': ()
        },

      # Responses
      { 'code': 41,
        'name': 'response_scanbus',
        'format': 'B32B',
        'format_comment': '<bus> (<idc> <bool>){16}',
        'deserializer': deserialize_scanbus_response,
        'str_func': str_scanbus_response
        },
      { 'code': 42,
        'name': 'response_read',
        'format': 'BBBi',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 43,
        'name': 'response_set',
        'format': 'BBBi',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 44,
        'name': 'response_mirror_read',
        'format': 'BBBi',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 45,
        'name': 'response_mirror_set',
        'format': 'BBBi',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 50,
        'name': 'response_bool',
        'format': '?',
        'format_args': ('bool_value',)
        },
      { 'code': 51,
        'name': 'response_error',
        'format': 'B',
        'format_args': ('error_code',),
        'str_func': str_error_response
        },

      # Notifications
      { 'code': 60,
        'name': 'notify_write_access',
        'format': '?',
        'format_args': ('bool_value',)
        },
      { 'code': 61,
        'name': 'notify_silent_mode',
        'format': '?',
        'format_args': ('bool_value',)
        },
      { 'code': 62,
        'name': 'notify_set',
        'format': 'BBBi',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 63,
        'name': 'notify_mirror_set',
        'format': 'BBBi',
        'format_args': ('bus', 'dev', 'par', 'val')
        },
      { 'code': 64,
        'name': 'notify_can_acquire_write_access',
        'format': '?',
        'format_args': ('bool_value',)
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

  @staticmethod
  def get_message_info(type_code_or_name):
    try:
      try:
        return MessageInfo.by_code[int(type_code_or_name)]
      except ValueError:
        return MessageInfo.by_name[str(type_code_or_name)]
    except (KeyError, ValueError):
      raise InvalidMessageType(type_code_or_name)

class ErrorInfo:
  info_list = [
      { 'code': 0,
        'name': 'unknown_error',
        'description': 'An unknown error occured.',
        },
      { 'code': 1,
        'name': 'invalid_message_type',
        'description': 'An invalid message type code was received.',
        },
      { 'code': 2,
        'name': 'invalid_message_size',
        'description': 'The transmitted message size did not match the expected message size.',
        },
      { 'code': 3,
        'name': 'bus_out_of_range',
        'description': 'The given bus number was out of range.',
        },
      { 'code': 4,
        'name': 'dev_out_of_range',
        'description': 'The given device address was out of range.',
        },
      { 'code': 5,
        'name': 'mrc_no_response',
        'description': 'The device did not respond. Most likely the bus address is not in use.',
        },
      { 'code': 6,
        'name': 'mrc_comm_timeout',
        'description': 'Timeout communicating with the MRC.',
        },
      { 'code': 7,
        'name': 'mrc_comm_error',
        'description': 'Non-timeout MRC communication error.',
        },
      { 'code': 8,
        'name': 'silenced',
        'description': 'Bus activity requested but silent mode is active.',
        },
      { 'code': 9,
        'name': 'mrc_connect_error',
        'description': 'The MRC connection could not be established.',
        },
      { 'code': 10,
        'name': 'permission_denied',
        'description': 'Permission denied. The client does not have write access.',
        },
      { 'code': 11,
        'name': 'mrc_parse_error',
        'description': 'MRC parse error.',
        },
      { 'code': 12,
        'name': 'mrc_address_conflict',
        'description': 'Address conflict detected.',
        },
      { 'code': 13,
        'name': 'request_canceled',
        'description': 'The request was canceled.',
        }
      ]

  by_name = {}
  by_code = {}

  for info in info_list:
    by_code[info['code']] = info
    by_name[info['name']] = info

  @staticmethod
  def get_error_names():
    return ErrorInfo.by_name.keys()

class Message(object):
  __slots__ = '_type_code', '_error_code', '_bus', '_dev', '_par', '_value', '_bool'

  def __init__(self, type_code, **kwargs):
    self._type_code = MessageInfo.get_message_info(type_code)['code']
    self._error_code = None

    for k,v in kwargs.iteritems():
      setattr(self, k, v)

  def get_type_info(self):
    return MessageInfo.get_message_info(self.type_code)

  def get_type_name(self):
    return self.get_type_info()['name']

  def is_request(self):
    return self.get_type_name().startswith('request_')

  def is_response(self):
    return self.get_type_name().startswith('response_')

  def is_notification(self):
    return self.get_type_name().startswith('notify_')

  def is_error(self):
    return self.get_type_name() == 'response_error'

  def get_error_code(self):
    return self._error_code

  def set_error_code(self, error_code):
    self._error_code = error_code

  def get_error_string(self):
    return ErrorInfo.by_code[self.get_error_code()]['name']

  def get_type_code(self): return self._type_code
  def get_bus(self): return self._bus
  def set_bus(self, bus):
    if 0 <= int(bus) < 2:
      self._bus = int(bus)
    else:
      raise MessageError("bus out of range", int(bus))

  def get_dev(self): return self._dev
  def set_dev(self, dev):
    if 0 <= int(dev) < 16:
      self._dev = int(dev)
    else:
      raise MessageError("dev out of range", int(dev))

  def get_par(self): return self._par
  def set_par(self, par):
    if 0 <= int(par) < 256:
      self._par = int(par)
    else:
      raise MessageError("par out of range", int(par))

  def get_value(self): return self._value
  def set_value(self, value):
    self._value = int(value)

  def get_bool(self): return self._bool
  def set_bool(self, value):
    self._bool = bool(value)

  type_code  = property(get_type_code)
  bus        = property(get_bus, set_bus)
  dev        = property(get_dev, set_dev)
  par        = property(get_par, set_par)
  val        = property(get_value, set_value)
  error_code = property(get_error_code, set_error_code)
  bool_value = property(get_bool, set_bool)

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
    if len(data) < 1:
      raise MessageError("deserialize(): empty data given")

    type_code = struct.unpack('!B', data[0])[0]
    type_info = MessageInfo.get_message_info(type_code)

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

class ScanbusResponse(Message):
  __slots__ = 'bus_data'

  def __init__(self, type_code, **kwargs):
    super(ScanbusResponse, self).__init__(type_code, **kwargs)

if __name__ == "__main__":
  msg = Message('request_read', bus=1, dev=2, par=3)

  serial_data = msg.serialize()
  msg_deserialized = Message.deserialize(serial_data)

  assert msg.get_type_name() == msg_deserialized.get_type_name()
  assert msg.bus == msg_deserialized.bus
  assert msg.dev == msg_deserialized.dev
  assert msg.par == msg_deserialized.par
  print msg_deserialized

  msg = ScanbusResponse('response_scanbus', bus=1, bus_data=[(27,1) for i in range(16)])
  print msg

  try:
    msg = Message('request_read', bus=3, dev=2, par=3)
  except MessageError:
    pass
  else:
    assert False

  try:
    msg = Message('request_read', bus=1, dev=16, par=3)
  except MessageError:
    pass
  else:
    assert False

  try:
    msg = Message('request_read', bus=1, dev=2, par=256)
  except MessageError:
    pass
  else:
    assert False

# vim:sw=2:sts=2
