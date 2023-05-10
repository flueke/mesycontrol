#!/usr/bin/env python

import signal
import sys
import time
from mesycontrol.script import get_script_context

def poll_volatile_parameters(mrc):
    for device in mrc.get_devices():
        # device is a script.DeviceWrapper instance
        # profile is a device_profile.DeviceProfile instance
        profile = ctx.get_device_profile(device.idc)
        print("bus={}, addr=0x{:x}, found device with idc={}, rc={}, type={}".format(
            device.bus, device.address, device.idc, "on " if device.rc else "off", profile.name), end='')

        if device.address_conflict:
            print(", address conflict detected!")
            continue

        volatiles = list(profile.get_volatile_addresses())
        print(": polling {} volatile parameters".format(len(volatiles)))

        for addr in volatiles:
            readResult = device.read_parameter(addr)
            paramProfile = profile[readResult.address]
            paramUnit = paramProfile.units[-1] # device_profile.Unit
            print("  addr={:03d}, raw_value={}, name={}, unit_value={} {}".format(
                readResult.address,
                readResult.value,
                paramProfile.name,
                paramUnit.unit_value(readResult.value),
                paramUnit.label))


g_quit = False

def signal_handler(signum, frame):
    g_quit = True

if __name__ == "__main__":
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
"""
    )
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)

    mrcUrl = sys.argv[1]

    with get_script_context() as ctx:
        ScanbusInterval = 5.0 # in seconds
        PollInterval = 1.0 # in seconds

        tScanbus = 0.0
        tPoll = 0.0

        mrc = ctx.make_mrc(mrcUrl)

        while not g_quit:
            if not mrc.is_connected():
                mrc.connectMrc()
                if mrc.is_connected():
                    print("Connected to mrc {}".format(mrcUrl))
            else:
                if time.monotonic() - tScanbus >= ScanbusInterval:
                    print("scanbus")
                    for bus in range(2):
                        mrc.scanbus(bus)
                    tScanbus = time.monotonic()

                if time.monotonic() - tPoll >= PollInterval:
                    print("poll")
                    poll_volatile_parameters(mrc)
                    tPoll = time.monotonic()
                else:
                    time.sleep(0.1)
