import signal
import logging
import subprocess
import sys
import time
try:
    import colorlog
except ImportError:
    colorlog = None
from mesycontrol import mrc_connection, util, server_process
from mesycontrol.qt import QtCore, Property

def do_connect(mrcCon, qapp):
    fres = mrcCon.connectMrc()
    logging.info(f"do_connect: got {fres=}")
    while not fres.done():
        qapp.processEvents()
    assert fres.result()

def do_disconnect(mrcCon, qapp):
    fres = mrcCon.disconnectMrc()
    while not fres.done():
        qapp.processEvents()
    assert fres.result()

def do_connection_test(mrcCon, qapp):
    for _ in range(3):
        assert mrcCon.is_disconnected()
        logging.warning("connect...")
        do_connect(mrcCon, qapp)
        # FIXME: there's a race here. without sleep the server will still do
        # scanbus polling. With the sleep it correctly detects that all clients
        # have disconnected and suspends scanbus polling. Maybe the server is
        # missing a 'QUIT' message or something from the client.
        time.sleep(1)
        logging.warning("disconnect...")
        do_disconnect(mrcCon, qapp);
        print("\n\n")

def do_server_process_test(qapp):
    server_options = { "serial_port": "/dev/ttyUSB0" }
    server_binary = "mesycontrol_server"
    server = server_process.pool.create_process(binary=server_binary, options=server_options)
    assert server is not None

    def start_server():
        print("Starting server...")
        fStart = server.start()
        while not fStart.done():
            qapp.processEvents()
        assert fStart.result()
        print("Server started")

    def stop_server():
        print("Stopping server...")
        fStop = server.stop()
        while not fStop.done():
            qapp.processEvents()
        assert fStop.result()
        print("Server stopped")

    for _ in range(10):
        start_server()
        stop_server()

def main():
    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)-8s] %(message)s')

    is_windows = sys.platform.startswith('win32')
    if colorlog and (not is_windows or colorama):
        fmt  = '%(bg_blue)s[%(asctime)-15s]%(reset)s '
        fmt += '[%(green)s%(name)s%(reset)s.%(log_color)s%(levelname)-8s%(reset)s] %(message)s'
        fmt  = colorlog.ColoredFormatter(fmt)
        hdlr = logging.getLogger().handlers[0]
        hdlr.setFormatter(fmt)

    # Signal handling
    def signal_handler(signum, frame):
        logging.info("Received signal %s. Quitting...",
                signal.signum_to_name.get(signum, "%d" % signum))
        qapp.quit()
        sys.exit(1)

    signal.signum_to_name = dict((getattr(signal, n), n)
            for n in dir(signal) if n.startswith('SIG') and '_' not in n)
    signal.signal(signal.SIGINT, signal_handler)

    qapp = QtCore.QCoreApplication(sys.argv)
    gc   = util.GarbageCollector()

    print(">>>>> server process test ==============================")
    do_server_process_test(qapp)
    print("<<<<< server process test ==============================")

    # Try a manually started server first to keep it simple.
    serverProc = subprocess.Popen(["mesycontrol_server", "--mrc-serial-port", "/dev/ttyUSB0"])
    time.sleep(1)
    mrcCon = mrc_connection.factory(url="mc://localhost")
    logging.info(f"Got {mrcCon=}")
    print(">>>>> connection with externally spawned server ========")
    do_connection_test(mrcCon, qapp)
    serverProc.terminate()
    print("<<<<< connection with externally spawned server ========")

    # Now use a LocalMrcConnetion which internally spawns a server
    mrcCon = mrc_connection.factory(url="serial:///dev/ttyUSB0")
    print(">>>>> connection with internally spawned server ========")
    do_connection_test(mrcCon, qapp)
    print("<<<<< connection with internally spawned server ========")

    sys.exit(0)


if __name__ == '__main__':
    main()
