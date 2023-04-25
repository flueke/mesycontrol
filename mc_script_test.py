from mesycontrol.script import get_script_context

with get_script_context() as ctx:
    mrc = ctx.make_mrc("mc://localhost:23000")
    print(mrc)
    mrc.connectMrc()
    print(mrc)

#from mesycontrol import script as mcs
#
## Direct server connection: "mc://localhost:23000"
## Have to spawn a server process: "/dev/ttyUSB0"
#
#with mcs.make_mrc("/dev/ttyUSB0") as mrc:
#    bus0_result = mrc.scanbus(0)
#    bus1_result = mrc.scanbus(1)
