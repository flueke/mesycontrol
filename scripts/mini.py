# Import the mesycontrol scripting functions
from mesycontrol.script import *

with get_script_context() as ctx:
    mrc = ctx.make_connection(url='/dev/ttyUSB0@0')
    assert mrc.connect(), "Connection failed"

    print "Bus configuration:"
    for i in range(2):
        print mrc[i]

    device = mrc[0][1] # Get device on bus 0 with address 1
    
    print "Device at (%d, %d): %s" % (0, 1, device)

    value = device[32] # Read address 32
    print "Value is %d" % value
