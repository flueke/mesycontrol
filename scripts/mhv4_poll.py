import datetime
from mesycontrol.script import *

row_fmt   = "{:>30}" + "{:>8}" * 4

def print_voltage_header():
    print row_fmt.format("Timestamp", *["Chan%d" % (i+1) for i in range(4)])

def print_voltages(mhv):
    voltages = [mhv[j+32] for j in range(4)]
    print row_fmt.format(str(datetime.datetime.now()), *voltages)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print "Print MHV4 voltages."
        print "Usage: %s <connection-url> <bus> <dev>" % sys.argv[0]
        print "Example: %s /dev/ttyUSB0@115200 0 1" % sys.argv[0]
        sys.exit(1)

    url = sys.argv[1]
    bus = int(sys.argv[2])
    dev = int(sys.argv[3])

    with get_script_context() as ctx:
        conn = ctx.make_connection(url=url)
        assert conn.connect()
        mhv  = conn.mrc[bus][dev]
        assert mhv.idc == 17

        print_voltage_header()
        i = 0
        while True:
            if i >= 30:
                print_voltage_header()
                i = 0
            i += 1
            print_voltages(mhv)
            Sleep(100)()
