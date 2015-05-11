#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

urls = ["/dev/ttyUSB0@9600;0/1", "serial:///dev/ttyUSB0:9600/0/1",
        "serial:///dev/ttyUSB0/0/1",
        "/dev/ttyUSB0@9600;0/1", "serial:///dev/ttyUSB0@9600;0/1",
        "serial:///dev/ttyUSB0;0/1",
        "tcp://localhost/0/1", "tcp://localhost:4001/0/1",
        "mc://localhost/0/1", "mc://localhost:20001/0/1",
        "/dev/ttyUSB0@9600?bus=0&dev=1"
        ]

import urlparse

for url in urls:
    p = urlparse.urlparse(url)
    print url, "\n", p, "\n"

print

for url in urls:
    p = urlparse.urlsplit(url)
    print url, "\n", p, p.username, p.password, p.port
    print p.path.split(";")

print

p = urlparse.urlunsplit(("serial", "/dev/ttyUSB0@9600", "0/1", "", ""))
print p, urlparse.urlsplit(p)

print

class ParseResult(urlparse.SplitResult):
    pass

for url in urls:
    p = urlparse.urlsplit(url)
    print p
    d = dict()
    if p.scheme is None:
        d['scheme'] = 'serial'


    if p.scheme is None:
        p.scheme = "serial"
    print d
