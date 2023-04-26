import time
from mesycontrol.script import get_script_context

with get_script_context() as ctx:

    mrc = ctx.make_mrc("mc://localhost:23000")
    mrc.connectMrc()

    print(f"Connected to MRC {mrc}")

    while mrc.is_connected():
        # Scan both busses. This updates the MRCs list of devices so the
        # scanbus operation has to run at least once for any devices to be
        # present in the MRC object.
        for bus in range(2):
            mrc.scanbus(bus)

        # For each found device get its profile from the context, then poll all
        # the volatile parameters specified in the profile.
        for device in mrc.get_devices():
            profile = ctx.get_device_profile(device.idc)
            print(f"Found device {device=} with device profile={profile}")

            addressesToPoll = profile.get_volatile_addresses()

            for addr in addressesToPoll:
                readResult = device.read_parameter(addr)
                paramName = profile[addr].name
                print(f"{device=}, {addr=}, {paramName=}, {readResult=}")

    #mscf = mrc[0][1]
    #print(f"{mscf=}, idc={mscf.get_idc()}")

    #mscfProfile = ctx.get_device_profile(mscf.idc)
    #print(f"{mscfProfile=}")

    #devices = mrc.get_devices()

    #print(f"devices={devices}")

#from mesycontrol import script as mcs
#
## Direct server connection: "mc://localhost:23000"
## Have to spawn a server process: "/dev/ttyUSB0"
#
#with mcs.make_mrc("/dev/ttyUSB0") as mrc:
#    bus0_result = mrc.scanbus(0)
#    bus1_result = mrc.scanbus(1)
