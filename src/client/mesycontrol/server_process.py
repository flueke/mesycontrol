#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import pyqtSignal
from functools import partial
import weakref

import util
from future import Future

class ServerError(Exception):
    pass

class ServerIsRunning(ServerError):
    pass

class ServerIsStopped(ServerError):
    pass

QProcess = QtCore.QProcess

class ServerProcess(QtCore.QObject):
    started  = pyqtSignal()
    error    = pyqtSignal(QProcess.ProcessError, str, int, str)
    finished = pyqtSignal(QProcess.ExitStatus, int, str)
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

    def __init__(self, binary='mesycontrol_server', listen_address='127.0.0.1', listen_port=23000,
            serial_port=None, baud_rate=0, tcp_host=None, tcp_port=4001, verbosity=3, parent=None):

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
        self.process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.process.started.connect(self.started)
        self.process.error.connect(self._error)
        self.process.finished.connect(self._finished)
        self.process.readyReadStandardOutput.connect(self._output)

    def start(self):
        ret = Future()

        try:
            if self.process.state() != QtCore.QProcess.NotRunning:
                raise ServerIsRunning()

            args = self._prepare_args()
            program = util.which(self.binary)

            if program is None:
                raise RuntimeError("Could not find server binary '%s'" % self.binary)

            # cmd_line = "%s %s" % (program, " ".join(args))

            def dc():
                self.process.started.disconnect(on_started)
                self.process.error.disconnect(on_error)

            def on_started():
                dc()
                ret.set_result(True)

            def on_error(error):
                dc()
                ret.set_exception(ServerError(error))

            self.process.started.connect(on_started)
            self.process.error.connect(on_error)

            self.log.debug("Starting %s %s", program, " ".join(args))
            self.process.start(program, args, QtCore.QIODevice.ReadOnly)

        except Exception as e:
            self.log.exception("ServerProcess")
            ret.set_exception(e)

        return ret

    def stop(self, kill=False):
        ret = Future()

        if self.process.state() != QtCore.QProcess.NotRunning:
            def on_finished(code, status):
                self.process.finished.disconnect(on_finished)
                self.log.debug("Process finished with code=%d (%s)", code, ServerProcess.exit_code_string(code))
                ret.set_result(True)

            self.process.finished.connect(on_finished)
            if not kill:
                self.process.terminate()
            else:
                self.process.kill()
        else:
            ret.set_exception(ServerIsStopped())
        return ret

    def kill(self):
        return self.stop(True)

    def is_starting(self):
        return self.process.state() == QtCore.QProcess.Starting

    def is_running(self):
        return self.process.state() == QtCore.QProcess.Running

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
        self.error.emit(error, self.process.errorString(), ServerProcess.exit_code_string(error))

    def _finished(self, code, status):
        self.finished.emit(status, code, ServerProcess.exit_code_string(code))

    def _output(self):
        data = str(self.process.readAllStandardOutput())
        self.output.emit(data)

class ServerProcessPool(QtCore.QObject):
    default_base_port = 23000

    def __init__(self, parent=None):
        super(ServerProcessPool, self).__init__(parent)
        self.log                = util.make_logging_source_adapter(__name__, self)
        self.base_port          = ServerProcessPool.default_base_port
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
        in_use = in_use.union(self._unavailable_ports)

        for p in xrange(self.base_port, 65535):
            if p not in in_use:
                return p

        raise RuntimeError("No listen ports available")

    def _on_process_finished(self, qt_exit_status, exit_code, exit_code_string, process):
        if exit_code_string == 'exit_address_in_use':
            self.log.warning('listen_port %d in use by an external process', process.listen_port)
            self._unavailable_ports.add(process.listen_port)
            del self._procs_by_port[process.listen_port]
            process.listen_port = self._get_free_port()
            self._procs_by_port[process.listen_port] = process
            process.start()

pool = ServerProcessPool()
