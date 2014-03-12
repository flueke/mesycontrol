#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

# Simple mesycontrol command line client.
# Requirements for the first version:
# - Connect to a mesycontrol server
# - Read user commands from stdin
# - Convert user commands to mesycontrol messages
# - Send message to the server
# - Receive response message
# - Print the response message to stdout
# - Supported commands: read, set, scanbus

import readline
import socket
import struct
import sys
from mesycontrol import Message

class Command:
    def __init__(self):
        pass

    def run(self, connection):
        data = self.msg.serialize();
        connection.sendall(struct.pack('!H', len(data)))
        connection.sendall(data)

        in_sz = struct.unpack('!H', connection.recv(2))[0]
        data  = connection.recv(in_sz)
        return Message.deserialize(data)

class ReadCommand(Command):
    def __init__(self, *args):
        Command.__init__(self)
        msg_type = 'request_read'
        if args[0] in ('read_mirror', 'rm'):
            msg_type = 'request_mirror_read'

        self.msg = Message(msg_type, bus=int(args[1]), dev=int(args[2]), par=int(args[3]))

class SetCommand(Command):
    def __init__(self, *args):
        Command.__init__(self)
        msg_type = 'request_set'
        if args[0] in ('set_mirror', 'sm'):
          msg_type = 'request_mirror_set'

        self.msg = Message(msg_type, bus=int(args[1]), dev=int(args[2]), par=int(args[3]), val=int(args[4]))


class ScanbusCommand(Command):
    def __init__(self, *args):
        Command.__init__(self)
        self.msg = Message('request_scanbus', bus=int(args[1]))

g_commands = {
        'read': ReadCommand,
        're': ReadCommand,
        'read_mirror': ReadCommand,
        'rm': ReadCommand,

        'set': SetCommand,
        'se': SetCommand,
        'set_mirror': SetCommand,
        'sm': SetCommand,

        'sc': ScanbusCommand,
        'scanbus': ScanbusCommand
        }

def parse_command(in_str):
    args = in_str.split()
    class_ = g_commands[args[0]]
    return class_(*args)

if __name__ == "__main__":
    socket.setdefaulttimeout(5)

    server_host = "localhost"
    server_port = 23000

    if len(sys.argv) > 1:
        server_host = sys.argv[1]

    if len(sys.argv) > 2:
        server_port = int(sys.argv[2])

    print "Connecting to %s:%d..." % (server_host, server_port),

    connection = socket.create_connection((server_host, server_port))
    connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    print "connected!"

    while True:
        in_line = raw_input("> ")
        if len(in_line) == 0:
            continue
        command = parse_command(in_line)
        output = command.run(connection)
        print output
