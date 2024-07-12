from __future__ import annotations
import sys
import typing

from mesycontrol.future import Future
from mesycontrol import util
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtWidgets
from mesycontrol.qt import Signal
from mesycontrol.server_process import ServerProcess, ServerError, ServerIsRunning, ServerIsStopped, ServerIsStarting, ServerIsStopping, ServerRuntimeError

QProcess = QtCore.QProcess

class Holder(QtCore.QObject):
    started  = Signal()

    def __init__(self, parent=None):
        super(Holder, self).__init__(parent)
        self.proc = QProcess()
        self.proc.setProcessChannelMode(QProcess.MergedChannels)

        def on_process_output():
            data = bytes(self.proc.readAllStandardOutput()).decode("unicode_escape")
            logging.info(f"process output: {data}")

        def on_process_started():
            logging.info("process started (signal)")
            self.started.emit()

        def on_process_error(error: QProcess.ProcessError):
            logging.info(f"on_process_error (signal): {error=}")

        def on_process_finished(exit_code: int, exit_status: QProcess.ExitStatus):
            logging.info(f"on_process_finished (signal): {exit_code=}, {exit_status=}")

        self.proc.readyReadStandardOutput.connect(on_process_output)
        self.proc.started.connect(on_process_started)
        self.proc.errorOccurred.connect(on_process_error)
        self.proc.finished.connect(on_process_finished)

    def start(self):
        program = 'mesycontrol_server'
        args = ['--version']
        self.proc.start(program, args, QtCore.QIODevice.ReadOnly)
        self.proc.waitForStarted()

    def waitForFinished(self):
        if self.proc.waitForFinished():
            print("waitForFinished returned true")
        else:
            print("waitForFinished returned false!")

        exit_code = self.proc.exitCode()
        exit_status = self.proc.exitStatus()

        print(f"process finished: {exit_code=}, {exit_status=}")

if __name__ == "__main__":
    import logging
    import sys

    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)-8s] %(message)s')

    qapp = QtWidgets.QApplication(sys.argv)

    #w = QtWidgets.QWidget()
    #w.setWindowTitle("foobar windowtitle")
    #w.show()
    #qapp.exec_()

    holder = Holder()

    holder.started.connect(lambda: print("started signal received"))


    holder.start()
    logging.info(f"state after start(): {holder.proc.state()}")
    if holder.proc.state() == QProcess.Running:
        print("process is running, waiting for it to finish")
        holder.waitForFinished()
    else:
        print("process is not running!")
