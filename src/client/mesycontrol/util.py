from PyQt4.QtCore import QObject, QTimer
import gc
import os
import sys
from mesycontrol import application_model

class GarbageCollector(QObject):
    '''
    Disable automatic garbage collection and instead collect manually
    every INTERVAL milliseconds.

    This is done to ensure that garbage collection only happens in the GUI
    thread, as otherwise Qt can crash.
    '''

    INTERVAL = 1000

    def __init__(self, parent=None, debug=False):
        QObject.__init__(self, parent)
        self.debug = debug

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check)

        self.threshold = gc.get_threshold()
        gc.disable()
        self.timer.start(self.INTERVAL)

    def check(self):
        #return self.debug_cycles() # uncomment to just debug cycles
        l0, l1, l2 = gc.get_count()
        if self.debug:
            print ('gc_check called:', l0, l1, l2)
        if l0 > self.threshold[0]:
            num = gc.collect(0)
            if self.debug:
                print ('collecting gen 0, found:', num, 'unreachable')
            if l1 > self.threshold[1]:
                num = gc.collect(1)
                if self.debug:
                    print ('collecting gen 1, found:', num, 'unreachable')
                if l2 > self.threshold[2]:
                    num = gc.collect(2)
                    if self.debug:
                        print ('collecting gen 2, found:', num, 'unreachable')

    def debug_cycles(self):
        gc.set_debug(gc.DEBUG_SAVEALL)
        gc.collect()
        for obj in gc.garbage:
            print (obj, repr(obj), type(obj))

# TODO: move this to ApplicationModel
def find_data_file(filename):
    return os.path.join(application_model.instance.data_dir, filename)

class URLParseError(Exception): pass

def parse_connection_url(url):
    """Parses the given connection URL.
    Returns a dictionary ready to be passed to mrc_connection.factory() to
    create a connection instance.
    Supported URL formats:
    - For serial connections:
        <serial_port>@<baud>
        serial://<serial_port>[@<baud=9600>]
    - For TCP connections (serial server connected to an MRC1):
        <host>:<port>
        tcp://<host>[:<port=4001>]
    - For connections to a mesycontrol server:
        mesycontrol://<host>[:<port=23000>]
    """
    proto, proto_sep, contents = url.partition('://')

    if len(proto_sep) == 0:
        # No protocol separator in url
        contents = url
        proto    = ""

    proto = proto.lower()

    serial_port, serial_sep, baud = contents.partition('@')
    host, host_sep, port          = contents.partition(':')

    if len(serial_sep) > 0 and len(baud) == 0:
        raise URLParseError("Missing baud rate after '@'")

    if len(host_sep) > 0 and len(port) == 0:
        raise URLParseError("Missing port after ':'")

    if proto == 'serial' or len(serial_sep) > 0:
        if len(serial_port) == 0:
            raise URLParseError("Empty serial port name")

        if len(baud) > 0:
            if not baud.isdigit():
                raise URLParseError("Non-numeric baud rate '%s'" % baud)
            baud = int(baud)
        else:
            baud = 9600
        return dict(serial_port=serial_port, baud_rate=baud)

    if len(proto) == 0 and len(port) == 0:
        raise URLParseError("Missing protocol or port")

    if len(proto) == 0:
        proto = 'tcp'

    if proto in ('tcp', 'mesycontrol'):
        if len(host) == 0:
            raise URLParseError("Empty host")

        if len(port) > 0:
            if not port.isdigit():
                raise URLParseError("Non-numeric port '%s'" % port)
            port = int(port)
        else:
            port = 4001 if proto == 'tcp' else 23000

        if proto == 'tcp':
            return dict(host=host, port=port)
        else:
            return dict(mesycontrol_host=host, mesycontrol_port=port)

    raise URLParseError("Invalid protocol '%s'" % proto)

