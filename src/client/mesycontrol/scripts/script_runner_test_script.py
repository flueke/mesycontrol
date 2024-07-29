# Example showing the structure of a script intended to be run through the
# script_runner.py tool included with mesycontrol.

# Invocation:
# - If mesycontrol is installed the mesycontrol_script_runner entrypoint can be used:
#   mesycontrol_script_runner /dev/ttyUSB0 path/to/script_runner_test_script.py [additional args]
# - Or directly via python3:
#   python3 script_runner.py /dev/ttyUSB0 path/to/script_runner_test_script.py [additional args]

import sys

def main(ctx, mrc, args):
    for bus in range(2):
        mrc.scanbus(bus)
        print(f"Scanned bus {bus} of mrc {mrc}")
        poll_volatile_parameters(ctx, mrc)

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
