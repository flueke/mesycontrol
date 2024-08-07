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

from __future__ import annotations

__author__ = 'Florian Lüke'
__email__  = 'f.lueke@mesytec.com'

from mesycontrol.qt import QtCore
from mesycontrol.qt import Signal
from enum import Enum, unique
from functools import partial
import collections
import weakref
import sys
import typing

from mesycontrol import util
from mesycontrol.future import Future

QProcess = QtCore.QProcess

BASE_PORT = 23000 #: The default port to listen on
MAX_PORT  = 65535 #: The maximum port number.

# The mesycontrol_server exit codes.
EXIT_CODES = {
        0:   "exit_success",
        10:  "exit_options_error",
        20:  "exit_address_in_use",
        30:  "exit_address_not_available",
        40:  "exit_permission_denied",
        50:  "exit_bad_listen_address",
        127: "exit_unknown_error"
        }

# How long to wait after process startup before checking if the process is
# still running. The server might exit right away if its listening port is in
# use.
STARTUP_DELAY_MS = 500

class ServerError(Exception):
    pass

class InternalServerError(ServerError):
    # For State violations
    pass

class ServerIsStarting(ServerError):
    pass

class ServerIsRunning(ServerError):
    pass

class ServerIsStopping(ServerError):
    pass

class ServerIsStopped(ServerError):
    pass

class ServerRuntimeError(ServerError):
    def __init__(self, error: QProcess.ProcessError):
        super(ServerRuntimeError, self).__init__()
        self.error = error

    def __str__(self):
        return f"ServerRuntimeError(error={self.error})"

def get_exit_code_string(exit_code):
    return EXIT_CODES.get(exit_code, "exit_unknown_error")

# Local listen ports and server startup:
# TODO: move the code that restart the server process with a different local
# port into ServerProcess itself and make it transparent for the user of the
# class. Meaning the classes user should not see started(), stopped(), error()
# or finished() signals while the ServerProcess is still trying to find a
# working listen port.

# Recording of used ports is wonky at best: it does not take the listen address
# into account at all. If it would then addresses like 0.0.0.0 would need
# special treatment as they won't work if e.g. the port is in use by a process
# listening only on 127.0.0.1. 0.0.0.0 needs the port on all interfaces...
# Just scrap the code recording used ports and start the server until a free
# base port for the address is found or we run out of ports.


@unique
class State(Enum):
    INIT = 0                # initial state, no process running
    START_PROCESS = 1       # start the process. can fail if e.g. the server binary cannot be found
    WAIT_FOR_STARTUP = 2    # QProcess startup
    WAIT_FOR_BIND = 3       # give the server some time to bind to its listen port
    CHECK_STATUS = 4        # check status of the launched process.
                            # exit_address_in_use ? incr port => START_PROCESS : RUNNING
    RUNNING = 5             # running. server should be ready to accept connections
    STOP_PROCESS = 6        # entered in stop() or kill(). process is being terminated


class ServerProcess(QtCore.QObject):
    finished = Signal(QProcess.ExitStatus, int, str) #: exit_status, exit_code, exit_code_string
    output   = Signal(str)

    startup_delay_ms = 200

    def __init__(self, binary='mesycontrol_server', listen_address='127.0.0.1', listen_port=BASE_PORT,
            serial_port=None, baud_rate=0, tcp_host=None, tcp_port=4001, verbosity=0,
            output_buffer_maxlen=10000, parent=None):

        super(ServerProcess, self).__init__(parent)

        self.log  = util.make_logging_source_adapter(__name__, self)

        self.binary = binary
        self.listen_address = listen_address
        self.listen_port = listen_port
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.verbosity = verbosity

        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.started.connect(self._started)
        self.process.errorOccurred.connect(self._errorOccured)
        self.process.finished.connect(self._finished)
        self.process.readyReadStandardOutput.connect(self._output)

        self.currentFuture: typing.Optional[Future] = None

        self._startup_delay_timer = QtCore.QTimer()
        self._startup_delay_timer.setSingleShot(True)
        self._startup_delay_timer.setInterval(ServerProcess.startup_delay_ms)
        self._startup_delay_timer.timeout.connect(self._on_startup_delay_expired)

        self.output_buffer = collections.deque(maxlen=output_buffer_maxlen)
        self.state = State.INIT

    def _do_start_process(self):
        assert self.state == State.START_PROCESS

        if self.state != State.START_PROCESS:
            raise InternalServerError(f"Attempting to start process in state {self.state}")

        program = util.which(self.binary)

        if program is None:
            raise ServerError("Could not find server binary '%s'" % self.binary)

        args = self._prepare_args()
        self.cmd_line = cmd_line = "%s %s" % (program, " ".join(args))

        # Only create a new future if we do not have one already.
        # _do_start_process() can be called multiple times during the
        # WAIT_FOR_BIND phase while the client still holds the future returnd
        # from start().
        if not self.currentFuture or self.currentFuture.done():
            self.currentFuture = Future()
            self.currentFuture.name = str(State.START_PROCESS)

        ret = self.currentFuture
        ret.set_progress_text(f"Starting ${cmd_line}")
        self.log.debug(f"Starting {cmd_line} ({self.currentFuture=})")

        self.state = State.WAIT_FOR_STARTUP
        self.process.start(program, args, QtCore.QIODevice.ReadOnly)
        return ret

    # Attempts to start the server. Raises ServerError if the process is already
    # running or another operation is in progress.
    # Otherwise returns a Future which will hold the result of the startup
    # operation.
    def start(self):
        # Startup procedure:
        # - start the server process and wait for it to emit started() or error()
        # - on error:   set result to ServerError
        # - on started: start a timer waiting for startup_delay_ms. This is to gives the
        #               server time to bind to its listen port.
        # - on timeout: if the process is still running: set result to True
        #               else set result to ServerError

        if self.state != State.INIT:
            raise ServerIsRunning(f"Attempting to start process in state {self.state}")

        self.state = State.START_PROCESS
        return self._do_start_process()

    # Stops the server process. Raises ServerError if the process is not running
    # or another operation is in progress.
    # Otherwise returns a Future which will hold the result of the stop
    # operation.
    def stop(self, kill=False):

        if self.state != State.RUNNING:
            raise ServerIsStopped(f"Attempting to stop process in state {self.state}")

        self.state = State.STOP_PROCESS
        self.currentFuture = ret = Future()

        if not kill:
            self.process.terminate()
        else:
            self.process.kill()

        return ret

    def waitForFinished(self, msecs: int = 30000):
        return self.process.waitForFinished(msecs)

    def kill(self):
        return self.stop(True)

    #def is_starting(self):
    #    return self.process.state() == QProcess.Starting

    def is_running(self):
        return self.process.state() == QProcess.Running

    def exit_code(self):
        code = self.process.exitCode()
        return (code, ServerProcess.exit_code_string(code))

    def get_internal_state(self):
        return self.state

    internal_state = property(get_internal_state)

    @staticmethod
    def exit_code_string(code):
        return EXIT_CODES.get(code, "exit_unknown_error")

    def _prepare_args(self):
        args = list()

        if self.verbosity != 0:
            # verbose/quiet flags (-vvv / -qqq)
            verb_flag = 'v' if self.verbosity > 0 else 'q'
            verb_args = '-' + verb_flag * abs(self.verbosity)
            args.append(verb_args)

        args.extend(['--listen-address', self.listen_address])
        args.extend(['--listen-port', str(self.listen_port)])

        if self.serial_port is not None:
            args.extend(['--mrc-serial-port', self.serial_port])
            args.extend(['--mrc-baud-rate', str(self.baud_rate)])
        elif self.tcp_host is not None:
            args.extend(['--mrc-host', self.tcp_host])
            args.extend(['--mrc-port', str(self.tcp_port)])
        else:
            raise ServerRuntimeError("Neither serial_port nor tcp_host given.")

        return args

    def _started(self):
        if self.state != State.WAIT_FOR_STARTUP:
            self.log.warn("ServerProcess._started() called in state %s", self.state)
            return

        self.log.debug("[pid=%s] Started %s; giving process time to bind()", self.process.pid(), self.cmd_line)

        self.state = State.WAIT_FOR_BIND
        self._startup_delay_timer.start()

    def _errorOccured(self, error):
        exit_code = self.process.exitCode()

        self.log.error("errorOccured=%d (%s), exit_code=%d (%s), state=%s",
                error, self.process.errorString(),
                exit_code, ServerProcess.exit_code_string(exit_code), self.state)

        if self.state == State.WAIT_FOR_STARTUP:
            self.state = State.INIT
            if self.currentFuture and not self.currentFuture.done():
                self.currentFuture.set_exception(ServerError(error))

    def _on_startup_delay_expired(self):
        self.log.debug(f"startup delay expired, state={self.state}")

        if self.state == State.WAIT_FOR_BIND:
            if self.process.state() == QProcess.Running:
                self.log.debug("startup delay expired, process is running")
                self.state = State.RUNNING
                if self.currentFuture is not None and not self.currentFuture.done():
                    self.currentFuture.set_progress_text("Started %s" % self.cmd_line)
                    self.currentFuture.set_result(True)
                return

            self.log.debug(f"startup delay expired, process is not running! exit_code={self.exit_code()}")

            # If the local listen address is in use. Increment the local port
            # number and try again.
            if self.exit_code()[1] == 'exit_address_in_use':
                self.log.info("listen address %s:%d is in use. Trying next local port...",
                        self.listen_address, self.listen_port)
                self.listen_port += 1
                self.state = State.START_PROCESS
                self._do_start_process()
            else:
                self.log.error("ServerProcess startup failed: %s", self.exit_code())
                self.state = State.INIT
                if self.currentFuture is not None and not self.currentFuture.done():
                    self.currentFuture.set_progress_text("Failed to start %s" % self.cmd_line)
                    self.currentFuture.set_result(False)

    def _finished(self, exit_code, exit_status):
        exit_code_string = ServerProcess.exit_code_string(exit_code)
        self.log.debug("_finished(): pid=%s finished: code=%d, status=%d (%s), state=%s",
                       self.process.pid(), exit_code, exit_status, exit_code_string, self.state)

        if self.state == State.STOP_PROCESS:
            self.state = State.INIT
            if self.currentFuture is not None and not self.currentFuture.done():
                self.currentFuture.set_progress_text("Stopped %s" % self.cmd_line)
                self.currentFuture.set_result(True)

    def _output(self):
        data = bytes(self.process.readAllStandardOutput()).decode("unicode_escape")
        self.output_buffer.append(data)

class ServerProcessPool(QtCore.QObject):
    """Keeps track of running ServerProcesses and the listen ports they use."""
    def __init__(self, parent=None):
        super(ServerProcessPool, self).__init__(parent)
        self.log                = util.make_logging_source_adapter(__name__, self)
        self._procs_by_port     = weakref.WeakValueDictionary()
        self._unavailable_ports = set()

    def create_process(self, options={}, binary='mesycontrol_server', parent=None):
        proc = ServerProcess(binary=binary, parent=parent)

        for attr, value in options.items():
            setattr(proc, attr, value)

        proc.listen_port = self._get_free_port()
        self._procs_by_port[proc.listen_port] = proc
        proc.finished.connect(partial(self._on_process_finished, process=proc))

        return proc

    def _get_free_port(self):
        in_use = set(self._procs_by_port.keys())
        self.log.debug("in_use=%s, unavail=%s", in_use, self._unavailable_ports)
        in_use = in_use.union(self._unavailable_ports)


        for p in range(BASE_PORT, 65535):
            if p not in in_use:
                return p

        raise RuntimeError("No listen ports available")

    def _on_process_finished(self, exit_status: QProcess.ExitStatus, exit_code: int, exit_code_string: str,
                             process: ServerProcess):
        pass

        self.log.debug("_on_process_finished: exit_code=%d (%s), exit_status=%d",
                exit_code, exit_code_string, exit_status)

        if exit_code_string == 'exit_address_in_use':
            self.log.warning('listen_port %d in use by an external process', process.listen_port)
            self._unavailable_ports.add(process.listen_port)
            del self._procs_by_port[process.listen_port]
            process.listen_port = self._get_free_port()
            self._procs_by_port[process.listen_port] = process
            process.start()

        elif exit_code != 0:
            pass
            #self.log.warning("ServerProcess finished with exit_code=%d (%s), exit_status=%d",
            #                exit_code, exit_code_string, exit_status)

pool = ServerProcessPool()

if __name__ == "__main__":
    import logging
    import signal

    logging.basicConfig(level=logging.INFO,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    app = QtCore.QCoreApplication([])

    def signal_handler(signum, frame):
        app.quit()
    signal.signal(signal.SIGINT, signal_handler)

    # Should succeed
    sp1 = ServerProcess(serial_port='/dev/ttyUSB0')
    # Should fail due to the serial port being in use. # FIXME: start() does return True!
    sp2 = ServerProcess(serial_port='/dev/ttyUSB0')
    # Both set to fail: exit_bad_listen_address and exit_address_not_available
    sp3 = ServerProcess(serial_port='/dev/ttyUSB0', listen_address="foobar")
    sp4 = ServerProcess(serial_port='/dev/ttyUSB0', listen_address="1.2.3.4")

    for sp in (sp1, sp2, sp3, sp4):
        def sp_start_done(f):
            print(f"start() done: {sp=} {f=}, {f.result()=}")

        f = sp.start().add_done_callback(sp_start_done)

        while not f.done():
            app.processEvents()

    sleepTime = 2000
    print(f"Started servers, sleeping in event loop for {sleepTime} ms")

    timer = QtCore.QTimer()
    timer.setInterval(sleepTime)
    timer.setSingleShot(True)
    timer.timeout.connect(app.quit)
    timer.start()

    ret = app.exec_()

    for sp in (sp1, sp2, sp3, sp4):
        def sp_stop_done(f):
            print(f"stop() done: {f}, {f.result()}")

        if sp.is_running():
            f = sp.stop().add_done_callback(sp_stop_done)
            while not f.done():
                app.processEvents()

    # Wait for the stop() call to finish. Alternatively the futures could be
    # used and polled.
    for sp in (sp1, sp2, sp3, sp4):
        while sp.is_running():
            app.processEvents()

    sys.exit(ret)
