#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import *
import util
import logging
import sys

class LogView(QtGui.QTextEdit):
    def __init__(self, parent=None):
        super(LogView, self).__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        self.formatter = logging.Formatter(
                '[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    def handle_log_record(self, log_record):
        self.append(self.formatter.format(log_record))

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')
    qapp = QtGui.QApplication(sys.argv)

    log_view = LogView()
    log_view.resize(400, 400)
    log_view.show()

    qt_logger = util.QtLogEmitter()
    qt_logger.log_record.connect(log_view.handle_log_record)
    logging.getLogger().addHandler(qt_logger.get_handler())

    logger = logging.getLogger(__name__)
    def on_button_clicked():
        logging.getLogger("testlogger").debug("Hello World!")

    button = QtGui.QPushButton("Log!", clicked=on_button_clicked)
    button.show()

    sys.exit(qapp.exec_())
