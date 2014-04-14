#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal
import logging
import os
from mesycontrol import application_model

class InvalidArgument(Exception):
    pass

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

    sig_started  = pyqtSignal()
    sig_error    = pyqtSignal(QtCore.QProcess.ProcessError)
    sig_finished = pyqtSignal(int, QtCore.QProcess.ExitStatus)
    sig_stderr   = pyqtSignal(str)
    sig_stdout   = pyqtSignal(str)

    def __init__(self, parent = None):
        super(ServerProcess, self).__init__(parent)

        self.binary_path     = application_model.instance.bin_dir
        self.binary_name     = ServerProcess.default_binary_name
        self.listen_address  = ServerProcess.default_listen_address
        self.listen_port     = ServerProcess.default_listen_port
        self.mrc_serial_port = None
        self.mrc_baud_rate   = ServerProcess.default_baud_rate
        self.mrc_host        = None
        self.mrc_port        = ServerProcess.default_mrc_port

        self.process = QtCore.QProcess(self)
        self.process.started.connect(self._slt_started)
        self.process.error.connect(self._slt_error)
        self.process.finished.connect(self._slt_finished)
        self.process.readyReadStandardError.connect(self._slt_stderr_ready)
        self.process.readyReadStandardOutput.connect(self._slt_stdout_ready)

        self.log = logging.getLogger("ServerProcess")

    def start(self):
        program = os.path.join(self.binary_path, self.binary_name)

        args = list()
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

        self._cmd_line = "%s %s" % (program, " ".join(args))

        self.log.info("Starting %s" % self._cmd_line)
        self.process.start(program, args, QtCore.QIODevice.ReadOnly)

    def stop(self, kill=False):
        if kill:
            self.process.kill()
        else:
            self.process.terminate()
        self.process.waitForFinished(1000)

    def is_running(self):
        return self.process.state() == QtCore.QProcess.Running

    def get_exit_code(self):
        return self.process.exitCode()

    def get_exit_code_string(self):
        return self.exit_codes.get(self.get_exit_code(), "exit_unknown_error")

    def _slt_started(self):
        self.log.info("Started %s => pid = %s" % (self._cmd_line, self.process.pid()))
        self.sig_started.emit()

    def _slt_error(self, process_error):
        self.log.error("Failed starting %s => error = %s" % (self._cmd_line, process_error))

    def _slt_finished(self, exit_code, exit_status):
        self.log.info("%s finished. exit_code = %s, exit_status = %s"
                % (self._cmd_line, exit_code, exit_status))
        self.sig_finished.emit(exit_code, exit_status)

    def _slt_stderr_ready(self):
        data = str(self.process.readAllStandardError())
        self.log.debug(data)
        self.sig_stderr.emit(data)

    def _slt_stdout_ready(self):
        data = str(self.process.readAllStandardOutput())
        self.log.debug(data)
        self.sig_stdout.emit(data)
