import sys
from mesycontrol.script import get_script_context

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

    mrcUrl = sys.argv[1]

    with get_script_context() as ctx:
        mrc = ctx.make_mrc(mrcUrl)
        mrc.connectMrc()
        mrc.scanbus(bus) # populates the 'devices' lists of the MRC

        # Find our MHV-4 by bus and address
        devices = mrc.get_devices(bus)
        mhv4 = next((d for d in devices if d.address == address))

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

            # Channel enable
            addr = mhv4_profile[f'channel{chan}_enable_write'].address
            mhv4.set_parameter(addr, enable)
