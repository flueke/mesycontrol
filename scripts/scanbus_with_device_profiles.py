#!/usr/bin/env python

import sys
from mesycontrol.script import get_script_context

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <mrc-url>")
    print(f"Example: {sys.argv[0]} /dev/ttyUSB0")
    sys.exit(1)

with get_script_context() as ctx:
    mrc = ctx.make_mrc(sys.argv[1])
    mrc.connectMrc()

    for bus in range(2):
        scanbusResult = mrc.scanbus(bus)

        for addr, entry in enumerate(scanbusResult):
            if entry.idc:
                print(f"{bus=}, {addr=}: found device with idc={entry.idc}, rc={entry.rc}", end='')
                if entry.conflict:
                    print(", address conflict detected!", end='')
                print()
