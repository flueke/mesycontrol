#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from mesycontrol.command import *
from mesycontrol.mrc_command import *
from mesycontrol.script import *

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: %s <script-file> [<script-args>]" % sys.argv[0]
        sys.exit(1)

    script_filename = sys.argv[1]
    script_globals  = globals()
    script_globals['sys'].argv = sys.argv[1:]
    execfile(script_filename, script_globals)
