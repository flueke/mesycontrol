#!/usr/bin/env python

import sys
from mesycontrol.script import get_script_context

def main():
    if len(sys.argv) != 2:
        print(f"""Usage: {sys.argv[0]} <mrc-url>

    Accepted mrc-url schemes:
        - For serial connections:
            <serial_port>@<baud> | serial://<serial_port>[@<baud>]
            e.g. /dev/ttyUSB0, /dev/ttyUSB0@115200
        - For TCP connections (serial server connected to an MRC1):
            <host>:<port>
            tcp://<host>[:<port=4001>]
        - For connections to a mesycontrol server:
            mc://<host>[:<port=23000>]
    """)
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

if __name__ == "__main__":
    main()
