#!/usr/bin/python
# -*- coding: utf8 -*-
# vim: ts=3 sts=3 sw=3
# MesytecControl - server and client to control Mesytec devices
# Copyright (C) 2013  Florian Lüke
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import asynchat
import asyncore
import getopt
import logging
import random
import socket
import sys

class MesytecDevice(object):
   def __init__(self, bus, port, id_):
      super(MesytecDevice, self).__init__()
      self.bus  = bus
      self.port = port
      self.id   = id_
      self.rc   = random.choice([True, False])
      self.params = dict((key, value) for (key, value) in ((i, 0) for i in range(256)))

   def setParameter(self, param, value):
      if not param in self.params:
         raise RuntimeError("unhandled param: %d" % param)
      self.params[param] = value

   def readParameter(self, param):
      if not param in self.params:
         raise RuntimeError("unhandled param: %d" % param)
      return self.params[param]

class MHV4(MesytecDevice):
   def __init__(self, bus, port):
      MesytecDevice.__init__(self, bus, port, 27)

      # max voltage (1 = 400V, 0 = 100V)
      self.params[45] = random.choice([0, 1])

      max_voltage = self.params[45] * 3000 + 1000

      for i in range(4):
         self.params[i]    = random.uniform(0, max_voltage) # target voltage
         self.params[i+32] = random.uniform(0, max_voltage) # actual voltage
         self.params[i+4]  = random.choice([True, False])   # channel on/off write
         self.params[i+36] = self.params[i+4]               # channel on/off read
         self.params[i+46] = random.choice([-1, 1])         # polarity read (read-only)
         self.params[i+8]  = random.uniform(0, 1000)        # current limit write
         self.params[i+40] = self.params[i+8]               # current limit read
         self.params[i+50] = random.uniform(-1000, 1000)    # current

class MSCF16(MesytecDevice):
   def __init__(self, bus, port):
      MesytecDevice.__init__(self, bus, port, 20)

      for i in range(5):                                    # groups 1 to 4 + common
         self.params[i]    = random.uniform(0, 15)          # gain
         self.params[i+39] = random.uniform(0, 3)           # shaping time

      for i in range(17):                                   # channels 1 to 16 + common
         self.params[i+5]  = random.uniform(0, 255)         # threshold
         self.params[i+22] = random.uniform(0, 255)         # pz value

      self.params[44]  = random.uniform(1, 8)               # mulitplicity hi
      self.params[45]  = random.uniform(1, 8)               # mulitplicity lo
      self.params[46]  = random.uniform(1, 16)              # monitor channel
      self.params[47]  = random.choice([True, False])       # single channel mode
      # RC on/off; the client expects to be able to read this although it's not
      # directly used as RC status is handled via scanbus command
      self.params[48]  = random.choice([True, False])       # RC on/off
      self.params[49]  = random.uniform(4*16, 6*16)         # version
      self.params[50]  = random.uniform(0, 255)             # BLR threshold
      self.params[51]  = random.choice([True, False])       # BLR on/off
      self.params[52]  = random.uniform(0, 255)             # coinc. time
      self.params[53]  = random.uniform(0, 200)             # threshold offset
      self.params[54]  = random.uniform(0, 200)             # shaper offset
      self.params[55]  = 0                                  # FIXME: sumdis threshold
      self.params[56]  = random.uniform(0, 255)             # PZ display range
      self.params[100] = 0                                  # auto PZ

class MCFD16(MesytecDevice):
   def __init__(self, bus, port):
      super(MCFD16, self).__init__(bus, port, 26)

class MRC1:
   def __init__(self):
      #self.busses = [[random.choice([MHV4(bus, port), MSCF16(bus, port), None])
      #   for port in range(16)] for bus in range(2)]

      self.busses = [[None for port in range(16)] for bus in range(2)]
      self.busses[0][0] = MHV4  (0, 0)
      self.busses[0][1] = MSCF16(0, 1)
      self.busses[1][0] = MHV4  (1, 0)
      self.busses[1][1] = MSCF16(1, 1)
      self.busses[1][2] = MCFD16(1, 2)
      self.prompt_enabled = True
      self.echo_enabled   = True

   def handle(self, data, connection_handler):
      self.conn = connection_handler

      if len(data) == 0:
         print "MRC1::handle: data length is 0!"
         self.output_error()
         self.output_prompt()
         return

      try:
         print "MRC1: handling:", data
         str_args = data.split()
         args = [int(arg) for arg in str_args[1:]]
         cmd = str_args[0].lower()

         if cmd == "sc":
            self.scanBus(bus=args[0])
         elif cmd == "se":
            self.setParameter(bus=args[0], port=args[1], param=args[2], value=args[3])
         elif cmd == "re":
            self.readParameter(bus=args[0], port=args[1], param=args[2])
         elif cmd == "rb":
            self.readMulti(bus=args[0], port=args[1], param=args[2], length=args[3])
         elif cmd in ["on", "off"]:
            self.rcOnOff(bus=args[0], port=args[1], cmd=cmd)
         elif cmd == "x0":
            self.echo_enabled = False
            print "echo disabled"
         elif cmd == "x1":
            self.echo_enabled = True
            print "echo enabled"
         elif cmd == "p0":
            self.prompt_enabled = False
            print "prompt disabled"
         elif cmd == "p1":
            self.prompt_enabled = True
            print "prompt enabled"
         else:
            raise RuntimeError("unhandled command '%s'" % cmd)
         self.output_prompt()
      except Exception:
         print data, "->", sys.exc_info()[1], "@ line", sys.exc_info()[2].tb_lineno
         self.output_error()

   def scanBus(self, bus):
      l = len(self.busses[bus])
      if self.echo_enabled:
         self.write_line("SC %d" % bus)
      self.write_line("ID-SCAN BUS %d:" % bus)
      for i in range(l):
         device = self.busses[bus][i]
         if device is not None:
            rc_out = "ON" if device.rc else "0FF"
            self.write_line("%d: %d, %s" % (i, device.id, rc_out))
         else:
            self.write_line("%d: -" % i)

   def rcOnOff(self, cmd, bus, port):
      rc = False
      if cmd == "on":
         rc = True

      self.busses[bus][port].rc = rc

      for i in range(2 if self.echo_enabled else 1):
         self.write_line("%s %d %d" % (cmd.upper(), bus, port))

   def readParameter(self, bus, port, param):
      value = self.busses[bus][port].readParameter(param)
      if self.echo_enabled:
         self.write_line("RE %d %d %d" % (bus, port, param))
      self.write_line("RE %d %d %d %d" % (bus, port, param, value))

   def readMulti(self, bus, port, param, length):
      if self.echo_enabled:
         self.write_line("RB %d %d %d %d" % (bus, port, param, length))

      if param + length > 256:
         raise RuntimeError("read multi request exceeds memory range")

      for i in range(length):
         self.write_line("%d" % (self.busses[bus][port].readParameter(param+i)))

   def setParameter(self, bus, port, param, value):
      self.busses[bus][port].setParameter(param, value)
      for i in range(2 if self.echo_enabled else 1):
         self.write_line("SE %d %d %d %d" % (bus, port, param, value))

   def write_line(self, data):
      print "output:", data
      self.conn.push(data + '\n\r')

   def output_error(self):
      self.write_line("ERROR!")

   def output_prompt(self):
      if self.prompt_enabled:
         self.conn.push("mrc-1>")

class MRC1ConnectionHandler(asynchat.async_chat):
   def __init__(self, sock, mrc1):
      asynchat.async_chat.__init__(self, sock)
      self.mrc1 = mrc1
      self.set_terminator("\r")
      self.ibuffer = []

   def collect_incoming_data(self, data):
      print "collect_incoming_data, data =", data
      self.ibuffer.append(data)

   def found_terminator(self):
      # data = "".join([s for s in self.ibuffer])
      print "found_terminator: len(self.ibuffer) before = ", len(self.ibuffer)
      data = "".join(self.ibuffer)
      print "found_terminator, len(data)=", len(data), " data=", data, " len(ibuffer) =", len(self.ibuffer)
      self.ibuffer = []
      self.mrc1.handle(data, self)

class MRC1Server(asyncore.dispatcher):
   def __init__(self, host, port, mrc1):
      asyncore.dispatcher.__init__(self)
      logging.info("Listening on %s:%d", host, port)
      self.mrc1 = mrc1
      self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
      self.set_reuse_addr()
      self.bind((host, port))
      self.listen(1)

   def handle_accept(self):
      pair = self.accept()
      if pair is not None:
         sock, addr = pair
         logging.info("Incoming connection from %s", repr(addr))
         handler = MRC1ConnectionHandler(sock, self.mrc1)

if __name__ == "__main__":
   host, port = "localhost", 4001

   logging.basicConfig(level=logging.DEBUG,
         format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

   try:
      opts, args = getopt.getopt(sys.argv[1:], 'h:p:')
   except getopt.GetoptError as e:
      print str(e)
      sys.exit(1)

   for o, a in opts:
      if o == "-h":
         host = a
      elif o == "-p":
         port = int(a)
      else:
         assert False, "unhandled option"

   mrc1   = MRC1()
   server = MRC1Server(host, port, mrc1)
   asyncore.loop()
