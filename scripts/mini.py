# Import the mesycontrol scripting functions
from mesycontrol.script import *

with get_script_context() as ctx:
    # do stuff here...
    connection = ctx.make_connection(url='/dev/ttyUSB0@115200')
    connection.connect()
    mrc = connection.mrc
    device = mrc[0][1] # Get device on bus 0 with address 1
    value = device[32] # Read address 32
    print "Value is %d" % value
