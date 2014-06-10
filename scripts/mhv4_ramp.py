import datetime
from mesycontrol.script import *

row_fmt   = "{:>30}" + "{:>8}" * 4

def print_voltage_header():
    print row_fmt.format("Timestamp", *["Chan%d" % (i+1) for i in range(4)])

def print_voltages(mhv):
    voltages = [mhv[j+32] for j in range(4)]
    print row_fmt.format(str(datetime.datetime.now()), *voltages)

def print_server_output(output):
    print "server: ", output

# Disables all channels and waits for ramp down to complete, then sets all MHV4
# channels to the given voltage and waits for the ramp up to reach the target
# voltage.
if __name__ == "__main__":
    if len(sys.argv) < 4:
        print "Usage: %s <connection-url> <bus> <dev> <target_voltage_v>" % sys.argv[0]
        print "Example: %s /dev/ttyUSB0@115200 0 1 350" % sys.argv[0]
        sys.exit(1)

    url = sys.argv[1]
    bus = int(sys.argv[2])
    dev = int(sys.argv[3])
    target_voltage = int(sys.argv[4])

    with get_script_context() as ctx:
        conn = ctx.make_connection(url=url)

        if hasattr(conn, 'server'):
            server_process = conn.server
            server_process.sig_stdout.connect(print_server_output)

        assert conn.connect(), "Connection failed"

        mrc = conn.mrc

        AcquireWriteAccess(mrc, force=True)()

        assert mrc.connection.has_write_access(), "Could not acquire mrc write access"

        print "Bus configuration:"
        for i in range(2):
            print mrc[i]

        mhv = mrc[bus][dev]
        
        assert mhv.idc == 17 # MHV4
        
        print "Disabling channels"
        for i in range(4):
            mhv[i+4] = 0 # disable channels
        
        print "Enabling RC"
        mhv.rc = True

        print "Channels disabled. Ramp down..."

        print_voltage_header()
        while True:
            print_voltages(mhv)
            voltages = [mhv[j+32] for j in range(4)]
            if all([v == 0 for v in voltages]): # True if all channels are at 0V
                break
            Sleep(500)() # Create and immediately exec a sleep command
        print

        target_voltage_raw = target_voltage * 10
        print "Setting channels to %dV (raw value=%d)" % (target_voltage, target_voltage_raw)
        for i in range(4):
            mhv[i] = target_voltage_raw
        
        print "Enabling channels"
        for i in range(4):
            mhv[i+4] = 1 # enable channels

        print "Channels enabled. Ramp up..."

        voltages = list()
        i = 0
        delay = 500
        sleep_cmd = Sleep(delay)
        for i in range(120):
            print_voltages(mhv)
            voltages = [mhv[j+32] for j in range(4)]
            if all([v == target_voltage_raw for v in voltages]): # True if all channels reached target_voltage_raw
                break
            sleep_cmd()

        print
        if all((v == target_voltage_raw for v in voltages)):
            print "Target voltages reached"
            sys.exit(0)
        else:
            print "Target voltages not reached after %ds. Final values: %s " % (
                    (i+1)*delay/1000.0, voltages)
            sys.exit(1)
