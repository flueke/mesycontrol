import sys
from mesycontrol.script import get_script_context

def main(ctx, mrc, args):
    # Bus and bus address of the target MCFD-16
    bus = 0
    address = 0xc

    # For each channel (enable, target_voltage [V])
    thresholds = (
        10,
        20,
        30,
        40,

        50,
        60,
        70,
        80,

        90,
        100,
        110,
        120,

        130,
        140,
        150,
        160,
    )

    mrc.scanbus(bus) # populates the 'devices' lists of the MRC

    # Find our MCFD-16 by bus and address
    devices = mrc.get_devices(bus)
    try:
        dev = next((d for d in devices if d.address == address))
    except StopIteration:
        print(f"Error: MCFD-16 not found on bus {bus}, address 0x{address:02x}")
        sys.exit(1)

    if dev.address_conflict:
        print(f"Error: Address conflict detected for {dev=}")
        sys.exit(1)

    # Load the device profile, in this case it's devices/mcfd16_profile.py
    dev_profile= ctx.get_device_profile(dev.idc)

    print(f"{dev=}, {dev_profile=}")

    if dev.idc != dev_profile.idc:
        print(f"Error: ID code mistmatch, wanted {dev_profile.idc=}, got {dev.idc=}")
        sys.exit(1)

    for (chan, threshold) in enumerate(thresholds):
        # Target threshold: param address lookup, then write to the mcfd16
        addr = dev_profile[f'threshold_channel{chan}'].address
        dev.set_parameter(addr, threshold)
        print(f"Set channel {chan} threshold to {threshold}")
