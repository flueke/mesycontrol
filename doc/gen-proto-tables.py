#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

# This script generates files containing mesycontrol protocol documentation
# tables in reStructuredText format. The files are included in the generated
# Sphinx documentation.
# Script arguments:
# 1. path to insert into sys.path to allow importing of the mesycontrol package
# 2. output path for the generated files
# e.g. python gen-proto-tables.py ~/src/mesycontrol/src/client ~/src/mesycontrol/build/doc/sphinx-source

from __future__ import print_function
import os
import string
import struct
import sys

def make_rst_table(column_titles, column_widths, data):
    row_fmt = "| {} " * len(column_widths) + "|"
    row_fmt = row_fmt.format(*["{:%d}" % w for w in column_widths])

    sep_fmt = "+{}" * len(column_widths) + "+"
    sep_fmt = sep_fmt.format(*["{:%d}" % (w+2) for w in column_widths])

    def make_separator_line(symbol):
        return sep_fmt.format(*[symbol*(w+2) for w in column_widths])

    def make_table_header(*names):
        strings = list()
        strings.append(make_separator_line('-'))
        strings.append(row_fmt.format(*column_titles))
        strings.append(make_separator_line('='))
        return '\n'.join(strings)

    lines = list()
    lines.append(make_table_header(*column_titles))

    for line_data in data:
        lines.append(row_fmt.format(*line_data))
        lines.append(make_separator_line('-'))

    return '\n'.join(lines)

if __name__ == '__main__':
    sys.path.insert(0, sys.argv[1])
    output_dir = sys.argv[2]

    from mesycontrol.protocol import ErrorInfo
    from mesycontrol.protocol import MessageInfo

# Requests
    requests   = filter(lambda info: info['name'].startswith('request'), MessageInfo.info_list)
    table_data = list()

    for request in requests:
        size = struct.calcsize(request['format'])
        fmt  = string.join([ "<%s>" % arg for arg in request['format_args'] ])
        table_data.append((request['name'], request['code'], size, fmt))

    with open(os.path.join(output_dir, 'protocol_requests.rst'), 'w') as f:
        print(make_rst_table(('**Name**', '**Code**', '**Size**', '**Format**'), (35, 8, 8, 35), table_data), file=f)

# Responses
    table_data = list()
    responses  = filter(lambda info: info['name'].startswith('response'), MessageInfo.info_list)

    for response in responses:
        size = 'variable'
        if 'format' in response:
            size = struct.calcsize(response['format'])
        fmt  = str()
        if 'format_args' in response:
            fmt  = string.join([ "<%s>" % arg for arg in response['format_args'] ])
        elif 'format_comment' in response:
            fmt = response['format_comment']
        table_data.append((response['name'], response['code'], size, fmt))

    with open(os.path.join(output_dir, 'protocol_responses.rst'), 'w') as f:
        print(make_rst_table(('**Name**', '**Code**', '**Size**', '**Format**'), (35, 8, 8, 35), table_data), file=f)

# Notifications
    table_data    = list()
    notifications = filter(lambda info: info['name'].startswith('notify'), MessageInfo.info_list)

    for notification in notifications:
        size = struct.calcsize(notification['format'])
        fmt  = string.join([ "<%s>" % arg for arg in notification['format_args'] ])
        table_data.append((notification['name'], notification['code'], size, fmt))

    with open(os.path.join(output_dir, 'protocol_notifications.rst'), 'w') as f:
        print(make_rst_table(('**Name**', '**Code**', '**Size**', '**Format**'), (35, 8, 8, 35), table_data), file=f)

# Error Codes
    table_data    = list()

    for error_info in ErrorInfo.info_list:
        table_data.append((error_info['name'], error_info['code'], error_info['description']))

    with open(os.path.join(output_dir, 'protocol_error_codes.rst'), 'w') as f:
        print(make_rst_table(('**Name**', '**Code**', '**Description**'), (35, 8, 100), table_data), file=f)
