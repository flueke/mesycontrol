import logging
import weakref
import sys
from mesycontrol import util
from mesycontrol.qt import QtCore
QProcess = QtCore.QProcess

program = util.which("mesycontrol_server")

def test1():
    args = [ "--mrc-serial-port", "/dev/ttyUSB0" ]
    cmd_line = "%s %s" % (program, " ".join(args))

    process = QProcess()
    process.setProcessChannelMode(QProcess.MergedChannels)
    process.start(program, args, QtCore.QIODevice.ReadOnly)
    if process.waitForFinished():
        print("process finished")
        print(process.readAll().data().decode())

def test2():
    args = [ "--mrc-serial-port", "/dev/ttyUSB0" ]
    cmd_line = "%s %s" % (program, " ".join(args))

    holder = QtCore.QObject()
    process = QProcess(parent=holder)
    process.setProcessChannelMode(QProcess.MergedChannels)
    process.start(program, args, QtCore.QIODevice.ReadOnly)
    holder.process = weakref.ref(process)
    return holder

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)-8s] %(message)s')
    print("Entering test1")
    test1()

    print("Entering test2")
    holder = test2()
    if holder.process().waitForFinished():
        print("process finished")
        print(holder.process().readAll().data().decode())
