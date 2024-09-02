import sys
from mesycontrol.script import script_runner_run

def main(ctx, mrc, args):
    # Bus and bus address of the target MHV-4
    bus = 0
    address = 0x02

    # For each channel (enable, target_voltage [V])
    channels = (
        (True,  10.0),
        (True,  20.0),
        (True,  30.0),
        (True,  40.0),
    )

    mrc.scanbus(bus) # populates the 'devices' lists of the MRC

    # Find our MHV-4 by bus and address
    devices = mrc.get_devices(bus)
    try:
        mhv4 = next((d for d in devices if d.address == address))
    except StopIteration:
        print(f"Error: MHV-4 not found on bus {bus}, address 0x{address:02x}")
        sys.exit(1)

    if mhv4.address_conflict:
        print(f"Error: Address conflict detected for {mhv4=}")
        sys.exit(1)

    # Load the device profile, in this case it's devices/mhv4_profile.py
    mhv4_profile = ctx.get_device_profile(mhv4.idc)

    print(f"{mhv4=}, {mhv4_profile=}")

    if mhv4.idc != mhv4_profile.idc:
        print(f"Error: ID code mistmatch, wanted {mhv4_profile.idc=}, got {mhv4.idc=}")
        sys.exit(1)

    for (chan, (enable, voltage)) in enumerate(channels):
        # Target voltage: param address lookup, then write to the mhv4
        addr = mhv4_profile[f'channel{chan}_voltage_write'].address
        mhv4.set_parameter(addr, voltage * 10)
        print(f"Set channel {chan} voltage to {voltage} V")

    for (chan, (enable, voltage)) in enumerate(channels):
        # Channel enable
        addr = mhv4_profile[f'channel{chan}_enable_write'].address
        mhv4.set_parameter(addr, enable)
        print(f"Set channel {chan} {'enabled' if enable else 'disabled'}")

if __name__ == "__main__":
    script_runner_run(main)
