#!/usr/bin/env python

# This script shows how to automatically poll all "volatile" (meaning possibly
# fast changing parameters) from all devices connected to the target MRC.
#
# The script periodically scans both MRC buses for devices. For each found
# device the mesycontrol DeviceProfile is looked up. All device parameters
# marked as "to be polled" are then read from the device using the MRC. For each
# parameter the associated ParameterProfile is loaded and uses to look up the
# parameter name, unit, unit conversion, etc. values.
#
# Found devices and parameter read results are printed to standard output.
# Press Ctrl-C to exit.

import signal
import sys
import time
from mesycontrol.script import get_script_context

def poll_volatile_parameters(ctx, mrc):
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

        print("Entering polling loop, press Ctrl-C to quit")

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
                    poll_volatile_parameters(ctx, mrc)
                    tPoll = time.monotonic()
                else:
                    time.sleep(0.1)

if __name__ == "__main__":
    main()
