from __future__ import annotations
import sys
import typing

from mesycontrol.future import Future
from mesycontrol import util
from mesycontrol.qt import QtCore
from mesycontrol.qt import Signal
from mesycontrol.server_process import ServerProcess, ServerError, ServerIsRunning, ServerIsStopped, ServerIsStarting, ServerIsStopping, ServerRuntimeError

QProcess = QtCore.QProcess

BASE_PORT = 23000 #: The default port to listen on
MAX_PORT  = 65535 #: The maximum port number.

class ServerProcess2(QtCore.QObject):
    started  = Signal()
    stopped  = Signal()
    error    = Signal(QProcess.ProcessError, str, int, str)
    finished = Signal(QProcess.ExitStatus, int, str) #: exit_status, exit_code, exit_code_string
    output   = Signal(str)

    startup_delay_ms = 200

    def __init__(self, binary='mesycontrol_server', listen_address='127.0.0.1', listen_port=BASE_PORT,
            serial_port=None, baud_rate=0, tcp_host=None, tcp_port=4001, verbosity=0,
            output_buffer_maxlen=10000, parent=None):

        super(ServerProcess2, self).__init__(parent)
        self.log  = util.make_logging_source_adapter(__name__, self)

        self.binary = binary
        self.listen_address = listen_address
        self.listen_port = listen_port
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.verbosity = verbosity

        self.startFuture: typing.Optional[Future] = None
        self.stopFuture: typing.Optional[Future] = None
        self.lastExitCode = None
        #self.process = QProcess(self)
        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        if 1:
            self.log.warning("using bound method!")
            self.process.started.connect(self._on_process_started)
            self.process.errorOccurred.connect(self._on_process_error)
            self.process.finished.connect(self._on_process_finished)
            self.process.readyReadStandardOutput.connect(self._on_process_output)
            self.process.destroyed.connect(self._on_process_destroyed)
        elif 0:
            self.log.warning("using bound lambdas!")
            l_on_started = lambda: self._on_process_started
            l_on_finished = lambda exit_code, exit_status: self._on_process_finished(exit_code, exit_status)
            l_on_error = lambda error: self._on_process_error(error)
            l_on_output = lambda: self._on_process_output()
            l_on_destroyed = lambda: self._on_process_destroyed()

            self.process.started.connect(l_on_started)
            self.process.finished.connect(l_on_finished)
            self.process.errorOccurred.connect(l_on_error)
            self.process.readyReadStandardOutput.connect(l_on_output)
            self.process.destroyed.connect(l_on_destroyed)

    def __del__(self):
        if not self.process.waitForFinished(5000):
            self.log.error("__del__(): child process did not finish!")

    def _on_process_destroyed(self):
        self.log.warning("c++ QProcess instance was destroyed just now!")

    def is_starting(self):
        return self.startFuture is not None

    def is_stopping(self):
        return self.stopFuture is not None

    def is_running(self):
        return self.process.state() == QProcess.Running

    def is_stopped(self):
        return not self.is_starting() and not self.is_stopping() and not self.is_running()

    def _on_process_started(self):
        self.log.debug("_on_process_started()")
        if self.startFuture is not None and not self.startFuture.done():
            self.startFuture.set_result(True)
            self.startFuture = None

        self.started.emit()

    def _on_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        self.log.debug("_on_process_finished()")
        if self.stopFuture is not None and not self.stopFuture.done():
            self.stopFuture.set_result((exit_code, exit_status))
            self.stopFuture = None

    def _on_process_error(self, error: QProcess.ProcessError):
        self.log.debug("_on_process_error()")
        if self.startFuture is not None and not self.startFuture.done():
            self.startFuture.set_exception(ServerRuntimeError(error))
            self.startFuture = None
        elif  self.stopFuture is not None and not self.stopFuture.done():
            self.stopFuture.set_exception(ServerRuntimeError(error))
            self.stopFuture = None

    def _on_process_output(self):
        data = bytes(self.process.readAllStandardOutput()).decode("unicode_escape")
        self.output.emit(data)

    def start(self):
        # TODO: use Qts started() and similar signals
        # TODO: implement the startup delay somehow

        ret = Future()

        if self.is_starting():
            ret.set_exception(ServerIsStarting())
            return ret

        if self.is_stopping():
            ret.set_exception(ServerIsStopping())
            return ret

        if self.is_running():
            ret.set_exception(ServerIsRunning())
            return ret

        program = util.which(self.binary)

        if program is None:
            ret.set_exception(ServerError(f"Could not find binary '{self.binary}' in PATH"))
            return ret

        args = self._prepare_args()
        cmd_line = "%s %s" % (program, " ".join(args))]
        self.process.start(program, args, QtCore.QIODevice.ReadOnly)
        self.startFuture = ret

        return ret

    def stop(self, kill=False):
        ret = Future()

        if self.is_starting():
            ret.set_exception(ServerIsStarting())
            return ret

        if self.is_stopping():
            ret.set_exception(ServerIsStopping())
            return ret

        if self.is_stopped():
            ret.set_exception(ServerIsStopped())
            return ret

        self.stopFuture = ret

        if kill:
            self.process.kill()
        else:
            self.process.terminate()

        return ret

    def kill(self):
        return self.stop(True)

    def waitForFinished(self, msecs: int = 30000):
        return self.process.waitForFinished(msecs)

    def exit_code(self):
        code = self.process.exitCode()
        return (code, ServerProcess.exit_code_string(code))

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

if __name__ == "__main__" and True:
    import logging
    import sys

    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)-8s] %(message)s')

    qapp = QtCore.QCoreApplication(sys.argv)

    proc = ServerProcess2(serial_port="/dev/ttyUSB0", verbosity=2)
    print("pre start()")
    f = proc.start()
    print(f"post start() {f=}")
    while not f.done():
        qapp.processEvents()
    print(f"start() done {f=}, {proc.is_starting()=}, {proc.is_stopping()=}, {proc.is_running()=}, {proc.is_stopped()=}")

    print(f"waiting for process to finish on its own")
    if proc.waitForFinished(2500):
        # TODO: record last exit code and status in the process object
        print(f"process finished.")
        print(f"{proc.is_starting()=}, {proc.is_stopping()=}, {proc.is_running()=}, {proc.is_stopped()=}")
    else:
        fKill = proc.kill().add_done_callback(lambda f: print("> kill done"))
        print(f"process did not finish, killing it! {fKill=}")
        # This is needed to keep the process alive for long enough
        while not fKill.done():
            proc.waitForFinished(2500)
        print(f"after attempting to kill process")

if __name__ == "__main__" and False:
    import logging
    import sys

    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)-8s] %(message)s')

    qapp = QtCore.QCoreApplication(sys.argv)

    proc = ServerProcess2(serial_port="/dev/ttyUSB0", verbosity=2)
