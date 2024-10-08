#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2021 mesytec GmbH & Co. KG <info@mesytec.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

__author__ = 'Florian Lüke'
__email__  = 'f.lueke@mesytec.com'

from pyqtgraph.SignalProxy import SignalProxy

from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui
from mesycontrol.qt import QtWidgets
from mesycontrol.qt import Signal
from mesycontrol.qt import Qt
from mesycontrol.qt import QUiLoader

QObject = QtCore.QObject
QTimer  = QtCore.QTimer

import contextlib
import collections.abc
import faulthandler
import gc
import logging
import math
import os
import re
import signal
import sys

from functools import reduce

HARDWARE = 1
CONFIG   = 2
COMBINED = 3

RW_MODE_NAMES = {
        HARDWARE: 'hardware',
        CONFIG: 'config',
        COMBINED: 'combined'
        }

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

class SocketError(Exception):
    def __init__(self, error_code, error_string):
        self.error_code   = int(error_code)
        self.error_string = str(error_string)

    def __str__(self):
        return self.error_string

    def __int__(self):
        return self.error_code

class Disconnected(Exception):
    def __str__(self):
        s = super(Disconnected, self).__str__()
        if not len(s):
            return "Disconnected"
        return s


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
        mc://<host>[:<port=23000>]
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

    if proto in ('tcp', 'mc'):
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
            return dict(mc_host=host, mc_port=port)

    raise URLParseError("Invalid protocol '%s'" % proto)

def display_url(url):
    if url.startswith("serial://"):
        return url[len("serial://"):]
    return url

def build_connection_url(serial_port=None, baud_rate=0, host=None, port=4001, mc_host=None, mc_port=23000):
    if serial_port:
        if baud_rate != 0:
            return "serial://%s@%d" % (serial_port, baud_rate)
        return "serial://%s" % serial_port

    if host:
        return "tcp://%s:%d" % (host, port)

    if mc_host:
        return "mc://%s:%d" % (mc_host, mc_port)

    raise ValueError("Invalid arguments given")

def mrc_urls_match(url1, url2):
    d1 = parse_connection_url(url1)
    d2 = parse_connection_url(url2)

    try:
        return d1['serial_port'] == d2['serial_port']
    except KeyError:
        return d1 == d2

def make_logging_source_adapter(module_name, object_instance):
    module_name = module_name.replace('mesycontrol.', str())
    logger_name = "%s.%s" % (module_name, object_instance.__class__.__name__)

    # Add the findCaller method to LoggerAdapter
    logging.LoggerAdapter.findCaller = lambda self: self.logger.findCaller()

    ret = logging.LoggerAdapter(
            logging.getLogger(logger_name),
            dict(source=id(object_instance)))

    return ret

SERIAL_USB    = 1
SERIAL_SERIAL = 2

def list_serial_ports(type_mask=SERIAL_USB | SERIAL_SERIAL):
    if sys.platform.startswith('linux'):
        return list_serial_ports_linux(type_mask)
    elif sys.platform.startswith('win32'):
        return list(list_serial_ports_windows(type_mask))

def list_serial_ports_linux(type_mask):
    import glob
    patterns = list()

    if type_mask & SERIAL_USB:
        patterns.extend(("/dev/ttyUSB?", "/dev/ttyUSB??"))

    if type_mask & SERIAL_SERIAL:
        patterns.extend(("/dev/ttyS?", "/dev/ttyS??"))

    ret = list()
    for p in patterns:
        ret.extend(sorted(glob.glob(p)))
    return ret

def list_serial_ports_windows(type_mask):
    """
    Uses the Win32 registry to return an iterator
    of serial (COM) ports existing on this computer.
    Source: http://eli.thegreenplace.net/2009/07/31/listing-all-serial-ports-on-windows-with-python/
    """
    import winreg
    import itertools
    path = 'HARDWARE\\DEVICEMAP\\SERIALCOMM'
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    except WindowsError:
        #raise StopIteration
        return # PEP-0479

    for i in itertools.count():
        try:
            val  = winreg.EnumValue(key, i)
            device, name = val[:2]

            serial_pattern = r"^.*Serial[0-9]+$"
            usb_pattern    = r"^.*VCP[0-9]+$"

            matches_serial = re.match(serial_pattern, device)
            matches_usb    = re.match(usb_pattern, device)

            if type_mask & SERIAL_SERIAL and matches_serial:
                yield name

            if type_mask & SERIAL_USB and matches_usb:
                yield name

            # names not matching the qualifiers above
            if not matches_serial and not matches_usb and type_mask & SERIAL_SERIAL:
                yield name

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

class MinimumLevelFilter(object):
    """Log records with a level greater or equal to minimum_level will pass
    through this filter."""
    def __init__(self, minimum_level):
        self.minimum_level = minimum_level

    def filter(self, log_record):
        return log_record.levelno >= self.minimum_level

class HasExceptionFilter(object):
    def filter(self, log_record):
        return log_record.exc_info is not None

class QtLoggingBridge(QObject):
    log_record = Signal(object)

    def __init__(self, parent=None):
        super(QtLoggingBridge, self).__init__(parent)

    def __call__(self, record):
        self.log_record.emit(record)

#class QtLogEmitter(QObject):
#    log_record = Signal(object)
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

    if sys.platform.startswith('win32') and not program.endswith('.exe'):
        program += '.exe'

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    log.debug("searching for '%s'", program)

    fpath, _ = os.path.split(program)
    if fpath:
        log.log(5, "checking %s", program)
        if is_exe(program):
            log.info("found %s", program)
            return program

    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        log.log(5, "checking %s", path)
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
            log.debug(f"emitter={emitting_callable}, signal={signal}: slot arguments match expected arguments")
            loop.exit(0)
        else:
            log.debug(f"emitter={emitting_callable}, signal={signal}: slot arguments do NOT match expected arguments")
            loop.exit(1)

    def on_timeout():
        log.debug(f"emitter={emitting_callable}, signal={signal}: timeout reached while waiting for signal (timeout={timeout_ms} ms)")
        loop.exit(1)

    signal.connect(the_slot)

    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(on_timeout)

    if emitting_callable is not None:
        log.debug(f"emitter={emitting_callable}, signal={signal}: invoking emitter")
        QtCore.QTimer.singleShot(0, emitting_callable)

    if timeout_ms > 0:
        log.debug(f"emitter={emitting_callable}, signal={signal}: starting timeout of {timeout_ms} ms")
        timer.start(timeout_ms)

    exitcode = loop.exec_()

    log.debug(f"emitter={emitting_callable}, signal={signal}: eventloop returned {exitcode}")

    timer.stop()
    timer.timeout.disconnect(on_timeout)
    signal.disconnect(the_slot)

    return exitcode == 0

@contextlib.contextmanager
def block_signals(o):
    was_blocked = False
    try:
        was_blocked = o.signalsBlocked()
        o.blockSignals(True)
        yield o
    finally:
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
    label = QtWidgets.QLabel(title)
    label.setFont(title_font)
    label.setAlignment(Qt.AlignCenter)
    return label

def hline(parent=None):
    ret = QtWidgets.QFrame(parent)
    ret.setFrameShape(QtWidgets.QFrame.HLine)
    ret.setFrameShadow(QtWidgets.QFrame.Sunken)
    return ret

def vline(parent=None):
    ret = QtWidgets.QFrame(parent)
    ret.setFrameShape(QtWidgets.QFrame.VLine)
    ret.setFrameShadow(QtWidgets.QFrame.Sunken)
    return ret

def make_spinbox(min_value=None, max_value=None, value=None, limits=None,
        prefix=None, suffix=None, single_step=None, parent=None):
    ret = QtWidgets.QSpinBox(parent)
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
class OrderedSet(collections.abc.MutableSet):

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

def loadUi(filename, parentWidget=None):
    """This version of PyQts uic.loadUi() adds support for loading from
    resource files."""
    f = QtCore.QFile(filename)
    if not f.open(QtCore.QIODevice.ReadOnly | QtCore.QIODevice.Text):
        raise RuntimeError(str(f.errorString()))
    return QUiLoader().load(f, parentWidget)

class ChannelGroupHelper(object):
    def __init__(self, num_channels, num_groups):
        self.num_channels = num_channels
        self.num_groups   = num_groups

    def channels_per_group(self):
        return int(self.num_channels / self.num_groups)

    def group_channel_range(self, group_num):
        return range(group_num * self.channels_per_group(),
                (group_num + 1) * self.channels_per_group())

    def channel_to_group(self, channel_num):
        return int(math.floor(channel_num / self.channels_per_group()))

class DelayedSpinBox(QtWidgets.QSpinBox):
    delayed_valueChanged = Signal(object)

    def __init__(self, delay=0.5, parent=None):
        super(DelayedSpinBox, self).__init__(parent)
        self.log = make_logging_source_adapter(__name__, self)

        def delayed_slt():
            self.log.debug("delayed_slt invoked. value=%d" % self.value())
            self.delayed_valueChanged.emit(self.value())

        self.proxy = SignalProxy(signal=self.valueChanged,
                slot=delayed_slt, delay=delay)

class DelayedDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    delayed_valueChanged = Signal(object)

    # Swapped order of arguments because of uic passing parent as first
    # argument if used in a .ui file...
    def __init__(self, parent=None, delay=0.5):
        super(DelayedDoubleSpinBox, self).__init__(parent)
        self.log = make_logging_source_adapter(__name__, self)

        def delayed_slt():
            self.log.debug("%s delayed_slt invoked. value=%d", self, self.value())
            self.delayed_valueChanged.emit(self.value())

        self.proxy = SignalProxy(signal=self.valueChanged,
                slot=delayed_slt, delay=delay)

        self.delayed_valueChanged.connect(self._on_delayed_valueChanged)

    def blockSignals(self, b):
        super(DelayedDoubleSpinBox, self).blockSignals(b)
        self.log.debug("%s proxy.block=%s", self, b)
        self.proxy.block = b

    def _on_delayed_valueChanged(self, value):
        self.log.debug("%s delayed_valueChanged(%s) emitted",
                self, value)

    def setValue(self, value):
        self.log.debug("%s setValue(%s)", self, value)
        super(DelayedDoubleSpinBox, self).setValue(value)

class FixedWidthVerticalToolBar(QtWidgets.QWidget):
    """Like a vertical QToolBar but having a fixed width. I did not manage to
    get a QToolBar to have a fixed width. That's the only reason this class
    exists."""
    def __init__(self, parent=None):
        super(FixedWidthVerticalToolBar, self).__init__(parent)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addStretch(1)

    def addAction(self, action):
        super(FixedWidthVerticalToolBar, self).addAction(action)
        b = QtWidgets.QToolButton()
        b.setDefaultAction(action)

        self.layout().takeAt(self.layout().count()-1)
        self.layout().addWidget(b, 0, Qt.AlignHCenter)
        self.layout().addStretch(1)
        self.setFixedWidth(self.sizeHint().width())

class SimpleToolBar(QtWidgets.QWidget):
    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super(SimpleToolBar, self).__init__(parent)
        self.orientation = orientation
        if orientation == Qt.Horizontal:
            self.setLayout(QtWidgets.QHBoxLayout())
        else:
            self.setLayout(QtWidgets.QVBoxLayout())

        self.layout().setSpacing(2)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addStretch(1)

    # Adds the action to the widget, creates a toolbutton linked to the action,
    # adds the toolbutton to the layout.
    # Returns the button created for the action.
    def addAction(self, action) -> QtWidgets.QToolButton:
        super(SimpleToolBar, self).addAction(action)
        b = QtWidgets.QToolButton()
        b.setDefaultAction(action)
        self.addWidget(b)
        return b

    def addWidget(self, widget):
        # Remove the stretch from the last position in the layout.
        self.layout().takeAt(self.layout().count()-1)
        self.layout().addWidget(widget)
        # Re-add the stretch as the last element in the layout.
        self.layout().addStretch(1)
        if self.orientation == Qt.Vertical:
            self.setFixedWidth(self.sizeHint().width())

def make_apply_common_button_layout(input_spinbox, tooltip, on_clicked):

    # Wrapper to invoke the clicked handler without the boolean arg that's
    # passed from QPushButton.clicked().
    def _on_clicked():
        on_clicked()

    button = QtWidgets.QPushButton(clicked=_on_clicked)
    button.setIcon(QtGui.QIcon(":/arrow-bottom.png"))
    button.setMaximumHeight(input_spinbox.sizeHint().height())
    button.setMaximumWidth(16)
    button.setToolTip(tooltip)

    layout = QtWidgets.QHBoxLayout()
    layout.addWidget(input_spinbox)
    layout.addWidget(button)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(1)

    return (layout, button)

def make_icon(source):
    return QtGui.QIcon(QtGui.QPixmap(source))

def make_standard_icon(icon, option=None, widget=None):
    return QtWidgets.QApplication.instance().style().standardIcon(icon, option, widget)

class ReadOnlyCheckBox(QtWidgets.QCheckBox):
    # Note: keyPressEvent and keyReleaseEvent do not need to be overriden
    # because FocusPolicy is set to NoFocus

    def __init__(self, *args, **kwargs):
        super(ReadOnlyCheckBox, self).__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.NoFocus)

    def mousePressEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()

# Source: https://stackoverflow.com/a/44351664
# Caution: this exhausts the iterator!
def ilen_destructive(iterable):
    return reduce(lambda result, _: result+1, iterable, 0)

# Copied from qutebrowser/misc/earlyinit.py (https://github.com/qutebrowser/qutebrowser)
def init_faulthandler(fileobj=sys.__stderr__):
    """Enable faulthandler module if available.
    This print a nice traceback on segfaults.
    We use sys.__stderr__ instead of sys.stderr here so this will still work
    when sys.stderr got replaced, e.g. by "Python Tools for Visual Studio".
    Args:
        fobj: An opened file object to write the traceback to.
    """
    try:
        faulthandler.enable(fileobj)
    except (RuntimeError, AttributeError) as e:
        # When run with pythonw.exe, sys.__stderr__ can be None:
        # https://docs.python.org/3/library/sys.html#sys.__stderr__
        #
        # With PyInstaller, it can be a NullWriter raising AttributeError on
        # fileno: https://github.com/pyinstaller/pyinstaller/issues/4481
        #
        # Later when we have our data dir available we re-enable faulthandler
        # to write to a file so we can display a crash to the user at the next
        # start.
        logging.getLogger().debug(f"Failed to enable early faulthandler: {e}", exc_info=True)
        return

    if (hasattr(faulthandler, 'register') and hasattr(signal, 'SIGUSR1') and
            sys.stderr is not None):
        # If available, we also want a traceback on SIGUSR1.
        # pylint: disable=no-member,useless-suppression
        faulthandler.register(signal.SIGUSR1)
        # pylint: enable=no-member,useless-suppression
