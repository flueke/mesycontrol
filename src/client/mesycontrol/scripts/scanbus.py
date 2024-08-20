#!/usr/bin/env python

from mesycontrol.script import script_runner_run

# The main() function is also loaded an called by mesycontrol_script_runner.
# The standalone() function is the entry point for the generated script in
# pyproject.toml.

def main(ctx, mrc, args):
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

if __name__ == "__main__":
    script_runner_run(main)
