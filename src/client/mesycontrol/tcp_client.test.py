import signal
import logging
import sys
try:
    import colorlog
except ImportError:
    colorlog = None
from mesycontrol import mrc_connection, util, server_process, tcp_client
from mesycontrol.qt import QtCore, Property

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


    for _ in range(5):
        client = tcp_client.MCTCPClient()
        fCon = client.connectClient("localhost", 23000)
        while not fCon.done():
            qapp.processEvents()
        print(f"Connected: {fCon.result()}")
        assert fCon.result()

        fDis = client.disconnectClient()
        while not fDis.done():
            qapp.processEvents()
        print(f"Disconnected: {fCon.result()}")
        assert fDis.result()


    sys.exit(0)

if __name__ == '__main__':
    main()
