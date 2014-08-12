from PyQt4.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal
from PyQt4.QtCore import Qt
import gc
import logging
import weakref

class NamedObject(QObject):
    sig_name_changed = pyqtSignal(str)

    def __init__(self, name=None, parent=None):
        super(NamedObject, self).__init__(parent)
        self.name = name

    def set_name(self, name):
        changed = False

        if name is None:
            changed = self.name is not None
            self.setObjectName("")
        else:
            changed = self.name != str(name)
            self.setObjectName(str(name))

        if changed:
            self.sig_name_changed.emit(self.name)

    def get_name(self):
        if self.objectName() is not None:
            return str(self.objectName())
        return None

    name = pyqtProperty(str, get_name, set_name, notify=sig_name_changed)
        
class TreeNode(QObject):
    """Support class for implementing the nodes of a Qt tree model."""
    def __init__(self, ref, parent=None):
        super(TreeNode, self).__init__(parent)
        self.ref         = ref
        self.children    = list()
        self._checkable  = False
        self._checkstate = Qt.Unchecked

    def get_ref(self):
        return self._ref() if self._ref is not None else None

    def set_ref(self, ref):
        self._ref = weakref.ref(ref) if ref is not None else None

    def get_row(self):
        if self.parent() is not None:
            return self.parent().children.index(self)
        return 0

    def flags(self, column):
        raise NotImplementedError()

    def data(self, column, role):
        raise NotImplementedError()

    def set_data(self, column, value, role):
        raise NotImplementedError()

    def context_menu(self):
        return None

    def set_checkable(self, on_off, recurse=True):
        self._checkable = on_off
        if recurse:
            for child in self.children:
                child.set_checkable(on_off, True)

    def is_checkable(self):
        return self._checkable

    def set_checkstate(self, check_state):
        self._checkstate = check_state

    def get_checkstate(self):
        return self._checkstate

    def find_node_by_ref(self, ref):
        if self.ref is ref:
            return self

        for c in self.children:
            ret = c.find_node_by_ref(ref)
            if ret is not None:
                return ret

        return None

    ref         = pyqtProperty(object, get_ref, set_ref)
    row         = pyqtProperty(int, get_row)
    checkable   = pyqtProperty(bool, is_checkable, set_checkable)
    check_state = pyqtProperty(Qt.CheckState, get_checkstate, set_checkstate)

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
        counts     = gc.get_count()
        thresholds = gc.get_threshold()

        if self.debug:
            print ('gc_check called:', counts)

        for i in range(len(counts)):
            if counts[i] > thresholds[i]:
                num = gc.collect(i)
                if self.debug:
                    print ('collecting gen %d, found: %d unreachable' % (i, num))
            else:
                break

    def debug_cycles(self):
        gc.set_debug(gc.DEBUG_SAVEALL)
        gc.collect()
        for obj in gc.garbage:
            print (obj, repr(obj), type(obj))

class URLParseError(Exception): pass

def parse_connection_url(url):
    # TODO: add support for baud rate auto detection. make e.g. '/dev/ttyUSB0'
    # pass and use auto baud rate. => assume a serial port if nothing else matches
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


class SourceFilter(object):
    """Logging filter using the log records 'source' attribute and a set of
    allowed sources to make the filtering decision.

    To make use of this filter create a LoggerAdapter with the 'source' keyword set:
    self.log = logging.LoggerAdapter(logging.getLogger(__name__), dict(source=weakref.ref(self)))

    Then add the objects you're interested in to the filter using add_source().
    make_logging_source_adapter() provides a shortcut for creating the LoggerAdapter.

    """
    def __init__(self):
        self.accepted_sources = weakref.WeakSet()

    def add_source(self, source):
        self.accepted_sources.add(source)

    def remove_source(self, source):
        self.accepted_sources.remove(source)

    def add_qobject_tree(self, root_obj):
        self.add_source(root_obj)
        for c in root_obj.children():
            self.add_qobject_tree(c)

    def filter(self, record):
        ret = (hasattr(record, 'source')
                and record.source is not None
                and record.source() is not None
                and record.source() in self.accepted_sources)
        return ret

def make_logging_source_adapter(logger_name, object_instance):
    return logging.LoggerAdapter(
            logging.getLogger(logger_name),
            dict(source=weakref.ref(object_instance)))

def list_serial_ports():
    import glob
    patterns = ("/dev/ttyUSB?", "/dev/ttyUSB??", "/dev/ttyS?", "/dev/ttyS??")
    ret      = list()
    for p in patterns:
        ret.extend(sorted(glob.glob(p)))
    return ret

class CallbackLoggingHandler(logging.Handler):
    def __init__(self, callback):
        super(CallbackLoggingHandler, self).__init__()
        self.callback = callback

    def emit(self, log_record):
        try:
            self.acquire()
            self.callback(log_record)
        finally:
            self.release()

class QtLogEmitter(QObject):
    log_record = pyqtSignal(object)

    def __init__(self, parent=None):
        super(QtLogEmitter, self).__init__(parent)
        self._handler = CallbackLoggingHandler(self.log_record.emit)

    def get_handler(self):
        return self._handler
