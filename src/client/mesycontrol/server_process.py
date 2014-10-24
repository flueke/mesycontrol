#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import QProcess
from PyQt4.QtCore import pyqtSignal, pyqtProperty
from functools import partial
import logging
import os
import util
import weakref

class InvalidArgument(Exception):
    pass

class QProcessWrapper(QProcess):
    def __init__(self, parent=None):
        super(QProcessWrapper, self).__init__(parent)

    #def setupChildProcess(self):
    #    """Called by Qt in the childs context just before the program is
    #    executed.
    #    Moves the child into its own process group to avoid receiving signals
    #    from the parent process.
    #    """
    #    os.setpgrp()

class ServerProcess(QtCore.QObject):
    exit_codes = {
            0:   "exit_success",
            1:   "exit_options_error",
            2:   "exit_address_in_use",
            3:   "exit_address_not_available",
            4:   "exit_permission_denied",
            5:   "exit_bad_listen_address",
            127: "exit_unknown_error"
            }

    default_binary_name    = "mesycontrol_server"
    default_listen_address = "127.0.0.1"
    default_listen_port    = 23000
    default_baud_rate      = 9600
    default_mrc_port       = 4001
    default_verbosity      = 3

    sig_started  = pyqtSignal()

    #: qt process error code, error string, system exit code, exit code string
    sig_error    = pyqtSignal(QProcess.ProcessError, str, int, str)

    #: qt exit status, system exit code, exit code string
    sig_finished = pyqtSignal(QProcess.ExitStatus, int, str)

    #: stdout and stderr of the child process
    sig_stdout   = pyqtSignal(str)

    def __init__(self, parent = None):
        super(ServerProcess, self).__init__(parent)
        import application_registry

        self.binary_path     = application_registry.instance.bin_dir
        self.binary_name     = ServerProcess.default_binary_name
        self.listen_address  = ServerProcess.default_listen_address
        self.listen_port     = ServerProcess.default_listen_port
        self.mrc_serial_port = None
        self.mrc_baud_rate   = ServerProcess.default_baud_rate
        self.mrc_host        = None
        self.mrc_port        = ServerProcess.default_mrc_port
        self.verbosity       = ServerProcess.default_verbosity

        self.process = QProcess()
        self.process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.process.started.connect(self._slt_started)
        self.process.error.connect(self._slt_error)
        self.process.finished.connect(self._slt_finished)
        self.process.readyReadStandardOutput.connect(self._slt_stdout_ready)

        self.log = util.make_logging_source_adapter(__name__, self)

    def start(self):
        if self.process.state() != QtCore.QProcess.NotRunning:
            return

        args = list()

        if self.verbosity != 0:
            # verbose/quiet flags (-vvv / -qqq)
            verb_flag = 'v' if self.verbosity > 0 else 'q'
            verb_args = '-' + verb_flag * abs(self.verbosity)
            args.append(verb_args)

        args.extend(['--listen-address', self.listen_address])
        args.extend(['--listen-port', str(self.listen_port)])

        if self.mrc_serial_port is not None:
            args.extend(['--mrc-serial-port', self.mrc_serial_port])
            args.extend(['--mrc-baud-rate', str(self.mrc_baud_rate)])
        elif self.mrc_host is not None:
            args.extend(['--mrc-host', self.mrc_host])
            args.extend(['--mrc-port', str(self.mrc_port)])
        else:
            raise InvalidArgument("Neither mrc_serial_port nor mrc_host set.")

        program = util.which(self.binary_name)

        if program is None:
            program = os.path.join(self.binary_path, self.binary_name)

        self.log.debug("Using server binary '%s'", program)

        self._cmd_line = "%s %s" % (program, " ".join(args))

        self.log.info("Starting %s", self._cmd_line)
        self.process.start(program, args, QtCore.QIODevice.ReadOnly)
        self.process.waitForStarted() # FIXME: remove this blocking call

    def stop(self, kill=False):
        if not self.is_running():
            return False

        if kill:
            self.process.kill()
        else:
            self.process.terminate()

        return True

    def is_running(self):
        return self.process.state() == QtCore.QProcess.Running

    def get_exit_code(self):
        return self.process.exitCode()

    def get_exit_code_string(self):
        return self.exit_codes.get(self.get_exit_code(), "exit_unknown_error")

    def get_verbosity(self):
        return self._verbosity

    def set_verbosity(self, verbosity):
        self._verbosity = int(verbosity)

    def get_info(self):
        if self.mrc_serial_port is not None:
            return "%s" % (self.mrc_serial_port, )
        elif self.mrc_host is not None:
            return "%s:%d" % (self.mrc_host, self.mrc_port)

    #: Set the server processes verbosity. Only affects newly started server
    #: processes.
    verbosity = pyqtProperty(int, get_verbosity, set_verbosity)

    def _slt_started(self):
        self.log.info("Started %s => pid = %s", self._cmd_line, self.process.pid())
        self.sig_started.emit()

    def _slt_error(self, process_error):
        self.log.error("Failed starting %s => error = %s: %s: %s",
                self._cmd_line, process_error, self.process.errorString(),
                    self.get_exit_code_string())

        self.sig_error.emit(process_error, self.process.errorString(),
                self.get_exit_code(), self.get_exit_code_string())

    def _slt_finished(self, exit_code, exit_status):
        self.log.info("%s finished. exit_code = %s, exit_status = %s => %s",
                self._cmd_line, exit_code, exit_status,
                    self.get_exit_code_string())

        self.sig_finished.emit(exit_status, exit_code, self.get_exit_code_string())

    def _slt_stdout_ready(self):
        data = str(self.process.readAllStandardOutput())
        for line in data.splitlines():
            self.log.debug(line)
            self.sig_stdout.emit(line)

class ProcessPool(QtCore.QObject):
    default_base_port = 23000

    def __init__(self, parent=None):
        super(ProcessPool, self).__init__(parent)
        self.log                = util.make_logging_source_adapter(__name__, self)
        self.base_port          = ProcessPool.default_base_port
        self._procs_by_port     = weakref.WeakValueDictionary()
        self._unavailable_ports = set()

    def create_process(self, options={}, parent=None):
        proc = ServerProcess(parent)

        for attr, value in options.iteritems():
            setattr(proc, attr, value)

        proc.listen_port = self._get_free_port()
        self._procs_by_port[proc.listen_port] = proc
        proc.sig_finished.connect(partial(self._slt_process_finished, process=proc))

        return proc

    def _get_free_port(self):
        in_use = set(self._procs_by_port.keys())
        in_use = in_use.union(self._unavailable_ports)

        for p in xrange(self.base_port, 65535):
            if p not in in_use:
                return p

        raise RuntimeError("No listen ports available")

    def _slt_process_finished(self, qt_exit_status, exit_code, exit_code_string, process):
        if exit_code_string == 'exit_address_in_use':
            self.log.warning('listen_port %d in use by an external process', process.listen_port)
            self._unavailable_ports.add(process.listen_port)
            process.listen_port = self._get_free_port()
            process.start()

pool = ProcessPool()

if __name__ == "__main__":
    import application_registry
    import sys

    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    app = QtCore.QCoreApplication(sys.argv)
    application_registry.instance = application_registry.ApplicationRegistry(
            sys.executable if getattr(sys, 'frozen', False) else __file__)

    procs = []
    for i in range(10):
        print "Starting processes"
        proc = pool.create_process(
                options={'mrc_serial_port': '/dev/ttyUSB0', 'mrc_baud_rate': 115200})
        proc.start()
        procs.append(proc)

    def stop_all():
        print "Stopping processes"
        for proc in procs:
            proc.stop()

    def stop_all_and_quit():
        stop_all()
        QtCore.QTimer.singleShot(5000, app.quit)

    QtCore.QTimer.singleShot(5000, stop_all_and_quit)

    ret = app.exec_()

    for proc in procs:
        if proc.is_running():
            print "Process still running!"

    sys.exit(ret)
