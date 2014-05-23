import datetime
from mesycontrol.command import *
from mesycontrol.mrc_command import *
from mesycontrol.script import *

def print_voltages(mhv, iterations, delay_ms):
    row_fmt   = "{:>3}{:>30}" + "{:>8}" * 4
    sleep_cmd = Sleep(delay_ms)

    print row_fmt.format("#", "Timestamp", *["Chan%d" % (i+1) for i in range(4)])

    for i in range(iterations):
        voltages = [mhv[j+32] for j in range(4)]
        print row_fmt.format(i+1, str(datetime.datetime.now()), *voltages)
        sleep_cmd.exec_()

# Toggles MHV4 channels and prints voltages repeatedly
if __name__ == "__main__":
    with get_script_context() as ctx:
        conn = ctx.make_connection(mesycontrol_host='localhost', mesycontrol_port='23000')
        conn = ctx.make_connection(host='localhost', port='4001')
        assert conn.connect(), "Connection failed"

        mrc = conn.mrc

        for i in range(2):
            print mrc[i]

        mhv = mrc[0][0] # device = mrc[bus][address]
        
        assert mhv.idc == 17 # 400V MHV4-4
        
        for i in range(4):
            mhv[i+4] = 0 # disable channels
        
        mhv.rc = True
        mhv[13] = 1 # set voltage range to 400V

        Sleep(200).exec_().get_result()
        assert mhv[45] == 1, "voltage range read"

        print "Voltage range set to 400V, channels disabled"
        print_voltages(mhv=mhv, iterations=20, delay_ms=500)
        print
        
        for i in range(4):
            mhv[i] = 3500 # set channel to 350V
        
        for i in range(4):
            mhv[i+4] = 1 # enable channels

        print "Channels enabled. Ramp up:"
        print_voltages(mhv=mhv, iterations=20, delay_ms=500)
