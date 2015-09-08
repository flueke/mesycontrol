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
    return msg.type == Message.RESP_ERROR

class MessageError(RuntimeError):
    def __init__(self, message=None, request=None, text=None, *args):
        super(MessageError, self).__init__(*args)
        self.message = message
        self.request = request
        self.text    = text

    def __str__(self):
        return "MessageError(%s, %s, %s)" % (
                self.message, self.request, self.text)

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
        'description': 'The device did not respond.',
        },
      { 'code': 6,
        'name': 'mrc_comm_timeout',
        'description': 'Timeout communicating with the MRC.',
        },
      { 'code': 7,
        'name': 'mrc_comm_error',
        'description': 'MRC communication error.',
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
        },
      { 'code': 14,
        'name': 'read_out_of_bounds',
        'description': 'The multi-read request exceeds the devices memory range.',
        },
      { 'code': 15,
        'name': 'mrc_connecting',
        'description': 'The MRC connection is being established.',
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

class MRCStatus:
  STOPPED, CONNECTING, CONNECT_FAILED, INITIALIZING, INIT_FAILED, RUNNING = range(6)

  info_list = [
      { 'code': 0,
        'name': 'stopped',
        'description': 'stopped',
        },
      { 'code': 1,
        'name': 'connecting',
        'description': 'connecting',
        },
      { 'code': 2,
        'name': 'connect_failed',
        'description': 'connection failed',
        },
      { 'code': 3,
        'name': 'initializing',
        'description': 'initializing',
        },
      { 'code': 4,
        'name': 'init_failed',
        'description': 'initialization failed',
        },
      { 'code': 5,
        'name': 'running',
        'description': 'running',
        },
      ]

  by_name = {}
  by_code = {}

  for info in info_list:
    by_code[info['code']] = info
    by_name[info['name']] = info
