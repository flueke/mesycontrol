#!/usr/bin/env python

import sys
from mesycontrol.script import get_script_context

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

    # Running the scanbus commands has the side effect of populating the
    # 'devices' data of the MRC.
    for bus in range(2):
        mrc.scanbus(bus)

    for device in mrc.get_devices():
        # device is a hardware_model.Device instance
        # profile is a device_profile.DeviceProfile instance
        profile = ctx.get_device_profile(device.idc)
        print("bus={}, addr=0x{:x}, found device with idc={}, rc={}, type={}".format(
            device.bus, device.address, device.idc, "on " if device.rc else "off", profile.name), end='')
        if device.address_conflict:
            print(", address conflict detected!", end='')
        print()
