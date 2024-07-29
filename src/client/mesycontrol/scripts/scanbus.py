#!/usr/bin/env python

import sys
from mesycontrol.script import get_script_context

def main(ctx, mrc, args):
    for bus in range(2):
        scanbusResult = mrc.scanbus(bus)

        for addr, entry in enumerate(scanbusResult):
            if entry.idc:
                print(f"{bus=}, {addr=}: found device with idc={entry.idc}, rc={entry.rc}", end='')
                if entry.conflict:
                    print(", address conflict detected!", end='')
                print()
