#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>
from qt import QtCore
from qt import QtGui
from qt import pyqtProperty
from qt import pyqtSignal
from qt import Qt

QObject = QtCore.QObject
QTimer  = QtCore.QTimer

import contextlib
import collections
import gc
import logging
import os
import sys
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
            baud = 0
        return dict(serial_port=serial_port, baud_rate=baud)

    if len(proto) == 0 and len(port) == 0:
        if not len(serial_port):
            raise URLParseError("Missing protocol or port")
        return dict(serial_port=serial_port, baud_rate=0)

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

def make_logging_source_adapter(module_name, object_instance):
    logger_name = "%s.%s" % (module_name, object_instance.__class__.__name__)

    return logging.LoggerAdapter(
            logging.getLogger(logger_name),
            dict(source=id(object_instance)))

def list_serial_ports():
    if sys.platform.startswith('linux'):
        return list_serial_ports_linux()
    elif sys.platform.startswith('win32'):
        return list(list_serial_ports_windows())

def list_serial_ports_linux():
    import glob
    patterns = ("/dev/ttyUSB?", "/dev/ttyUSB??", "/dev/ttyS?", "/dev/ttyS??")
    ret      = list()
    for p in patterns:
        ret.extend(sorted(glob.glob(p)))
    return ret

def list_serial_ports_windows():
    """
    Uses the Win32 registry to return an iterator
    of serial (COM) ports existing on this computer.
    Source: http://eli.thegreenplace.net/2009/07/31/listing-all-serial-ports-on-windows-with-python/
    """
    import _winreg as winreg
    import itertools
    path = 'HARDWARE\\DEVICEMAP\\SERIALCOMM'
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    except WindowsError:
        raise StopIteration

    for i in itertools.count():
        try:
            val = winreg.EnumValue(key, i)
            yield str(val[1])
        except EnvironmentError:
            break

class CallbackHandler(logging.Handler):
    """Logging handler passing log_records to callbacks."""
    def __init__(self):
        super(CallbackHandler, self).__init__()
        self._callbacks = list()

    def add_callback(self, callback):
        self._callbacks.append(callback)

    def remove_callback(self, callback):
        self._callbacks.remove(callback)

    def get_callbacks(self):
        return list(self._callbacks)

    def __len__(self):
        return len(self._callbacks)

    def emit(self, log_record):
        try:
            self.acquire()
            for callback in self._callbacks:
                try:
                    callback(log_record)
                except:
                    pass
        finally:
            self.release()

class QtLoggingBridge(QObject):
    log_record = pyqtSignal(object)

    def __init__(self, parent=None):
        super(QtLoggingBridge, self).__init__(parent)

    def __call__(self, record):
        self.log_record.emit(record)

#class QtLogEmitter(QObject):
#    log_record = pyqtSignal(object)
#
#    def __init__(self, parent=None):
#        super(QtLogEmitter, self).__init__(parent)
#        self._handler = CallbackLoggingHandler(self.log_record.emit)
#
#    def get_handler(self):
#        return self._handler

# source: http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python/377028#377028
def which(program):
    log = logging.getLogger("%s.%s" % (__name__, "which"))

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    log.debug("searching for '%s'", program)

    fpath, fname = os.path.split(program)
    if fpath:
        log.debug("checking %s", program)
        if is_exe(program):
            log.debug("found %s", program)
            return program

    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        log.debug("checking %s" % path)
        exe_file = os.path.join(path, program)
        if is_exe(exe_file):
            log.debug("found %s", exe_file)
            return exe_file

    log.debug("could not find binary for %s", program)
    return None

class AnyValue(object):
    pass

# Inspired by waitForSignal() from https://github.com/hlamer/enki/blob/master/tests/base.py
def wait_for_signal(signal, expected_args=None, timeout_ms=0, emitting_callable=None):
    """Uses a local Qt event loop to wait for the given signal to arrive.

    expected_args specifies which arguments are expected once the signal is
    emitted. If expected_args is None any arguments are valid. To specify a
    placeholder argument use the AnyValue class above (put the class directly
    into the argument sequence, don't instantiate it).

    timeout_ms gives the maximum time in milliseconds to wait for the signal.
    If 0 this function will wait forever.

    emitting_callable can be used to pass a callable object to the function.
    This callable will be invoked from within the internal event loop. This is
    neccessary to avoid missing signals connected via Qt's direct connection
    mechanism (the signal would arrive before the event loop was started and
    thus it would be missed completely).

    The return value is True if the signal arrived within the given timeout and
    with the correct arguments. Otherwise False is returned.
    """

    log = logging.getLogger(__name__ + '.wait_for_signal')

    def do_args_match(expected, given):
        if len(expected) != len(given):
            return False

        combined = zip(expected, given)

        for exp_arg, given_arg in combined:
            if exp_arg == AnyValue:
                continue

            if exp_arg != given_arg:
                return False

        return True

    loop = QtCore.QEventLoop()

    def the_slot(*args):
        if expected_args is None or do_args_match(expected_args, args):
            log.debug("slot arguments match expected arguments")
            loop.exit(0)
        else:
            log.debug("slot arguments do not match expected arguments")
            loop.exit(1)

    def on_timeout():
        log.debug("timeout reached while waiting for signal")
        loop.exit(1)

    signal.connect(the_slot)

    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(on_timeout)

    if emitting_callable is not None:
        log.debug("invoking emitter %s", emitting_callable)
        QtCore.QTimer.singleShot(0, emitting_callable)

    if timeout_ms > 0:
        log.debug("starting timer with timeout=%d", timeout_ms)
        timer.start(timeout_ms)

    exitcode = loop.exec_()

    log.debug("eventloop returned %d", exitcode)

    timer.stop()
    timer.timeout.disconnect(on_timeout)
    signal.disconnect(the_slot)

    return exitcode == 0

@contextlib.contextmanager
def block_signals(o):
    was_blocked = o.signalsBlocked()
    o.blockSignals(True)
    yield o
    o.blockSignals(was_blocked)

class ExceptionHookRegistry(object):
    """Exception handler registry for use with sys.excepthook.
    Contains a list of handler objects which will get called in the order they
    where registered when an exception occurs.
    """
    def __init__(self):
        self._handlers = list()

    def register_handler(self, handler):
        self._handlers.append(handler)

    def unregister_handler(self, handler):
        self._handlers.remove(handler)

    def get_handlers(self):
        return list(self._handlers)

    def __len__(self):
        return len(self._handlers)

    def __call__(self, exc_type, exc_value, exc_trace):
        for handler in self._handlers:
            handler(exc_type, exc_value, exc_trace)

def make_title_label(title):
    title_font = QtGui.QFont()
    title_font.setBold(True)
    label = QtGui.QLabel(title)
    label.setFont(title_font)
    label.setAlignment(Qt.AlignCenter)
    return label

def hline(parent=None):
    ret = QtGui.QFrame(parent)
    ret.setFrameShape(QtGui.QFrame.HLine)
    ret.setFrameShadow(QtGui.QFrame.Sunken)
    return ret

def vline(parent=None):
    ret = QtGui.QFrame(parent)
    ret.setFrameShape(QtGui.QFrame.VLine)
    ret.setFrameShadow(QtGui.QFrame.Sunken)
    return ret

def make_spinbox(min_value=None, max_value=None, value=None, limits=None,
        prefix=None, suffix=None, single_step=None, parent=None):
    ret = QtGui.QSpinBox(parent)
    if min_value is not None:
        ret.setMinimum(min_value)
    if max_value is not None:
        ret.setMaximum(max_value)
    if limits is not None:
        ret.setMinimum(limits[0])
        ret.setMaximum(limits[1])
    if prefix is not None:
        ret.setPrefix(prefix)
    if suffix is not None:
        ret.setSuffix(suffix)
    if single_step is not None:
        ret.setSingleStep(single_step)
    if value is not None:
        ret.setValue(value)

    return ret

# http://code.activestate.com/recipes/576694/
class OrderedSet(collections.MutableSet):

    def __init__(self, iterable=None):
        self.end = end = [] 
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        if key in self.map:        
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)
