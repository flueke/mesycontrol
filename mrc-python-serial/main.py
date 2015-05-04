#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import random
import serial

# Purpose: Test and play with MRC serial communication and make it work with
# prompt (p1) and echo (x1) enabled.

def serial_read(port):
    data = str()
    b = port.read(1)
    while len(b):
        data += str(b)
        b = port.read(512)
    return data

ser = serial.Serial(port='/dev/ttyUSB0', baudrate=115200, timeout=.1)

print "+++ Initial read"
data = serial_read(ser)
print repr(data)
print "\n+++Initial read done (%d chars)" % len(data)

print "+++ Initial write (\\r)"
ser.write("\r")
data = serial_read(ser)
print repr(data)
print "\n+++Initial write done (read %d chars)" % len(data)

print "+++ Turning echo off"
ser.write("X0\r")
print repr(serial_read(ser))
print "+++ Echo off"

print "+++ Turning prompt on"
ser.write("P1\r")
print repr(serial_read(ser))
print "+++ Prompt on"

commands = ["?", "SC 0", "SC 1", "LI", "PS", "garbage", "X0", "X1", "RE 0 1 0"]

for i in range(10000000):
    command = random.choice(commands)
    ser.write(command + "\r")
    data = serial_read(ser)
    print data
    assert data[-6:] == "mrc-1>"
