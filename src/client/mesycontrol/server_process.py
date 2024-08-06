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
        self.process.error.connect(self._error)
        self.process.started.connect(self._started)
        self.process.finished.connect(self._finished)
        self.process.readyReadStandardOutput.connect(self._output)

        self.lastExitCode = 0
        self.lastExitSatus = QProcess.ExitStatus.NormalExit
        self.lastError = typing.Optional[QProcess.ProcessError]
        self.currentFuture: typing.Optional[Future] = None

        self._startup_delay_timer = QtCore.QTimer()
        self._startup_delay_timer.setSingleShot(True)
        self._startup_delay_timer.setInterval(ServerProcess.startup_delay_ms)
        self._startup_delay_timer.timeout.connect(self._on_startup_delay_expired)

        # State
        self.output_buffer = collections.deque(maxlen=output_buffer_maxlen)
        self.program = str()
        self.cmd_line = str() # for logging only

    def _do_start_process(self):
        program = util.which(self.binary)
        args = self._prepare_args()

        self.process.start(program, args, QtCore.QIODevice.ReadOnly)

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

        if self.currentFuture is not None and not self.currentFuture.done():
            raise ServerError("Operation in progress")

        if self.process.state() != QProcess.NotRunning:
            raise ServerIsRunning()

        try:
            self.lastExitCode = 0
            self.lastExitStatus = QProcess.ExitStatus.NormalExit
            self.currentFuture = ret = Future()

            self.args = args = self._prepare_args()
            self.program = program = util.which(self.binary)

            if program is None:
                raise ServerError("Could not find server binary '%s'" % self.binary)

            self.cmd_line = cmd_line = "%s %s" % (program, " ".join(args))
            self.log.debug("Starting %s", cmd_line)
            ret.set_progress_text("Starting %s" % cmd_line)
            self._do_start_process()
            #self.process.start(program, args, QtCore.QIODevice.ReadOnly)

        except Exception as e:
            self.log.exception("ServerProcess.start()")
            if self.currentFuture is not None and not self.currentFuture.done():
                self.currentFuture.set_exception(e)

        return ret

    # Stops the server process. Raises ServerError if the process is not running
    # or another operation is in progress.
    # Otherwise returns a Future which will hold the result of the stop
    # operation.
    def stop(self, kill=False):
        if self.currentFuture is not None and not self.currentFuture.done():
            raise ServerError("Operation in progress")

        if self.process.state() == QProcess.NotRunning:
            raise ServerIsStopped()

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

    def is_starting(self):
        return self.process.state() == QProcess.Starting

    def is_running(self):
        return self.process.state() == QProcess.Running

    def exit_code(self):
        code = self.lastExitCode
        if self.process is not None:
            code = self.process.exitCode()
        return (code, ServerProcess.exit_code_string(code))

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
            raise RuntimeError("Neither serial_port nor tcp_host given.")

        return args

    def _started(self):
        self.log.debug("[pid=%s] Started %s", self.process.pid(), self.cmd_line)
        self._startup_delay_timer.start()

    def _on_startup_delay_expired(self):
        if self.currentFuture and not self.currentFuture.done():
            if self.process.state() != QProcess.Running:
                self.log.debug(f"startup delay expired, exit_code={self.exit_code()}")
                self.currentFuture.set_exception(ServerError(self.exit_code()))
            else:
                self.log.debug("startup delay expired, process is running")
                self.currentFuture.set_progress_text("Started %s" % self.cmd_line)
                self.currentFuture.set_result(True)

    def _error(self, error):
            self.lastError = error
            if self.currentFuture and not self.currentFuture.done():
                self.currentFuture.set_exception(ServerError(error))

        #exit_code = self.process.exitCode()
        #self.log.error("error=%d (%s), exit_code=%d (%s)",
        #        error, self.process.errorString(),
        #        exit_code, ServerProcess.exit_code_string(exit_code))

        #self.lastExitCode = exit_code

    def _finished(self, exit_code, exit_status):
        exit_code_string = ServerProcess.exit_code_string(exit_code)
        self.log.debug("_finished(): pid=%s finished: code=%d, status=%d (%s)",
                       self.process.pid(), exit_code, exit_status, exit_code_string)

        # The local listen address is in use. Increment the local port number
        # and try again.
        if exit_code_string == 'exit_address_in_use':
            self.log.info("listen address %s:%d is in use. Trying next local port...",
                    self.listen_address, self.listen_port)
            self.listen_port += 1
            self._do_start_process()
        else:
            self.lastExitCode = exit_code
            self.lastExitStatus = exit_status
            self.finished.emit(exit_status, exit_code, ServerProcess.exit_code_string(exit_code))
            if self.currentFuture and not self.currentFuture.done():
                self.currentFuture.set_result(exit_code == 0)

    def _output(self):
        data = bytes(self.process.readAllStandardOutput()).decode("unicode_escape")
        #print("--->", data)
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

    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    app = QtCore.QCoreApplication([])

    def signal_handler(signum, frame):
        app.quit()
    signal.signal(signal.SIGINT, signal_handler)

    sp1 = ServerProcess(serial_port='/dev/ttyUSB0')
    sp2 = ServerProcess(serial_port='/dev/ttyUSB0')
    sp3 = ServerProcess(serial_port='/dev/ttyUSB0', listen_address="foobar")
    sp4 = ServerProcess(serial_port='/dev/ttyUSB0', listen_address="1.2.3.4")

    def sp_start_done(f):
        print("start() done:", f.result())

    sp1.start().add_done_callback(sp_start_done)
    sp2.start().add_done_callback(sp_start_done)
    sp3.start().add_done_callback(sp_start_done)
    sp4.start().add_done_callback(sp_start_done)

    sys.exit(app.exec_())
