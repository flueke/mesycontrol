#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import pyqtSignal
from functools import partial
import collections
import weakref
import sys

import util
from future import Future

QProcess = QtCore.QProcess

BASE_PORT = 23000 #: The default port to listen on
MAX_PORT  = 65535 #: The maximum port number.

# The mesycontrol_server exit codes.
EXIT_CODES = {
        0:   "exit_success",
        1:   "exit_options_error",
        2:   "exit_address_in_use",
        3:   "exit_address_not_available",
        4:   "exit_permission_denied",
        5:   "exit_bad_listen_address",
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
    started  = pyqtSignal()
    stopped  = pyqtSignal()
    error    = pyqtSignal(QProcess.ProcessError, str, int, str)
    finished = pyqtSignal(QProcess.ExitStatus, int, str) #: exit_status, exit_code, exit_code_string
    output   = pyqtSignal(str)

    exit_codes = {
            0:   "exit_success",
            1:   "exit_options_error",
            2:   "exit_address_in_use",
            3:   "exit_address_not_available",
            4:   "exit_permission_denied",
            5:   "exit_bad_listen_address",
            127: "exit_unknown_error"
            }

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
        self.process.finished.connect(self._finished)
        self.process.readyReadStandardOutput.connect(self._output)

        self._startup_delay_timer = QtCore.QTimer()
        self._startup_delay_timer.setSingleShot(True)
        self._startup_delay_timer.setInterval(ServerProcess.startup_delay_ms)

        self.output_buffer = collections.deque(maxlen=output_buffer_maxlen)

    def start(self):
        # Startup procedure:
        # - start the server process and wait for it to emit started() or error()
        # - on error: set result to ServerError
        # - on started: start a timer waiting for startup_delay_ms
        # - on timeout: if the process is still running: set result to True
        #               else set result to ServerError
        ret = Future()

        try:
            if self.process.state() != QProcess.NotRunning:
                raise ServerIsRunning()

            args = self._prepare_args()
            program = util.which(self.binary)

            if program is None:
                raise ServerError("Could not find server binary '%s'" % self.binary)

            cmd_line = "%s %s" % (program, " ".join(args))

            def dc():
                self.process.started.disconnect(on_started)
                self.process.error.disconnect(on_error)
                self.process.finished.disconnect(on_finished)

            def on_started():
                self.log.debug("[pid=%s] Started %s", self.process.pid(), cmd_line)
                dc()
                self._startup_delay_timer.timeout.connect(on_startup_delay_expired)
                self._startup_delay_timer.start()

            def on_error(error):
                self.log.debug("Error starting %s: %d", error)
                dc()
                ret.set_exception(ServerError(error))

            def on_finished(exit_code, exit_status):
                self.log.debug("%s finished: code=%d, status=%d", exit_code, exit_status)

            def on_startup_delay_expired():
                self._startup_delay_timer.timeout.disconnect(on_startup_delay_expired)

                if self.process.state() == QProcess.Running:
                    self.started.emit()
                    self.log.debug("[pid=%s] Startup delay expired", self.process.pid())
                    ret.set_progress_text("Started %s" % cmd_line)
                    ret.set_result(True)
                else:
                    if self.process.error() != QProcess.UnknownError:
                        self.log.warning("Setting exception with errorString: %s", self.process.errorString())
                        ret.set_exception(ServerError(self.process.errorString()))
                    else:
                        self.log.warning("Setting exception with exit_code: %s", self.exit_code())
                        ret.set_exception(ServerError(self.exit_code()))

            self.process.started.connect(on_started)
            self.process.error.connect(on_error)
            self.process.finished.connect(on_finished)

            self.log.debug("Starting %s", cmd_line)
            self.process.start(program, args, QtCore.QIODevice.ReadOnly)

            ret.set_progress_text("Starting %s" % cmd_line)

        except Exception as e:
            #self.log.exception("ServerProcess")
            ret.set_exception(e)

        return ret

    def stop(self, kill=False):
        ret = Future()

        if self.process.state() != QProcess.NotRunning:
            def on_finished(code, status):
                self.log.debug("Process finished with code=%d (%s)", code, ServerProcess.exit_code_string(code))
                self.process.finished.disconnect(on_finished)
                ret.set_result(True)

            self.process.finished.connect(on_finished)
            if not kill and not sys.platform.startswith('win32'):
                self.process.terminate()
            else:
                self.process.kill()
        else:
            ret.set_exception(ServerIsStopped())
        return ret

    def kill(self):
        return self.stop(True)

    def is_starting(self):
        return self.process.state() == QProcess.Starting

    def is_running(self):
        return self.process.state() == QProcess.Running

    def exit_code(self):
        code = self.process.exitCode()
        return (code, ServerProcess.exit_code_string(code))

    @staticmethod
    def exit_code_string(code):
        return ServerProcess.exit_codes.get(code, "exit_unknown_error")

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

    def _error(self, error):
        exit_code = self.process.exitCode()
        self.log.error("error=%d (%s), exit_code=%d (%s)",
                error, self.process.errorString(),
                exit_code, ServerProcess.exit_code_string(exit_code))

        self.error.emit(error, self.process.errorString(),
                exit_code, ServerProcess.exit_code_string(exit_code))

    def _finished(self, code, status):
        self.log.debug("Finished: status=%d, code=%d, str=%s", status, code,
                ServerProcess.exit_code_string(code))
        self.finished.emit(status, code, ServerProcess.exit_code_string(code))

    def _output(self):
        data = str(self.process.readAllStandardOutput())
        self.output_buffer.append(data)
        self.output.emit(data)

class ServerProcessPool(QtCore.QObject):
    """Keeps track of running ServerProcesses and the listen ports they use."""
    def __init__(self, parent=None):
        super(ServerProcessPool, self).__init__(parent)
        self.log                = util.make_logging_source_adapter(__name__, self)
        self._procs_by_port     = weakref.WeakValueDictionary()
        self._unavailable_ports = set()

    def create_process(self, options={}, parent=None):
        proc = ServerProcess(parent=parent)

        for attr, value in options.iteritems():
            setattr(proc, attr, value)

        proc.listen_port = self._get_free_port()
        self._procs_by_port[proc.listen_port] = proc
        proc.finished.connect(partial(self._on_process_finished, process=proc))

        return proc

    def _get_free_port(self):
        in_use = set(self._procs_by_port.keys())
        self.log.debug("in_use=%s, unavail=%s", in_use, self._unavailable_ports)
        in_use = in_use.union(self._unavailable_ports)


        for p in xrange(BASE_PORT, 65535):
            if p not in in_use:
                return p

        raise RuntimeError("No listen ports available")

    def _on_process_finished(self, exit_status, exit_code, exit_code_string, process):

        self.log.debug("_on_process_finished: exit_code=%d (%s), exit_status=%d",
                exit_code, exit_code_string, exit_status)

        if exit_code_string == 'exit_address_in_use':
            self.log.warning('listen_port %d in use by an external process', process.listen_port)
            self._unavailable_ports.add(process.listen_port)
            del self._procs_by_port[process.listen_port]
            process.listen_port = self._get_free_port()
            self._procs_by_port[process.listen_port] = process
            process.start()

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
        print "start() done:", f.result()

    sp1.start().add_done_callback(sp_start_done)
    sp2.start().add_done_callback(sp_start_done)
    sp3.start().add_done_callback(sp_start_done)
    sp4.start().add_done_callback(sp_start_done)

    sys.exit(app.exec_())
