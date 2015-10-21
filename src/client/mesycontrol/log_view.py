#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import QtGui
import logging
import sys
import time
import traceback

import util

class LogView(QtGui.QTextEdit):
    def __init__(self, max_lines=10000, line_wrap=QtGui.QTextEdit.WidgetWidth, parent=None):
        super(LogView, self).__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(max_lines)
        self.setLineWrapMode(line_wrap)

        self.formatter = logging.Formatter(
                fmt='%(asctime)s %(name)s: %(message)s',
                datefmt='%H:%M:%S')

        self._mutex = QtCore.QMutex()
        self._original_text_color = self.textColor()

    def append(self, text, prepend_time=True):
        if prepend_time:
            str_time = time.strftime("%H:%M:%S")
            super(LogView, self).append(str_time + ": " + text)
        else:
            super(LogView, self).append(text)

        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def handle_log_record(self, log_record):
        with QtCore.QMutexLocker(self._mutex):
            try:
                if log_record.levelno >= logging.ERROR:
                    self.setTextColor(QtGui.QColor("#ff0000"))

                self.append(self.formatter.format(log_record), prepend_time=False)
            finally:
                self.setTextColor(self._original_text_color)

    def handle_exception(self, exc_type, exc_value, exc_trace):
        with QtCore.QMutexLocker(self._mutex):
            try:
                self.setTextColor(QtGui.QColor("#ff0000"))
                lines = exc_value.traceback_lines
                self.append("".join(lines).strip())
            except AttributeError:
                self.append("".join(traceback.format_exception(exc_type, exc_value, exc_trace)).strip())
            finally:
                self.setTextColor(self._original_text_color)

    def contextMenuEvent(self, event):
        pos  = event.globalPos()
        menu = self.createStandardContextMenu(pos)
        menu.addAction("Clear").triggered.connect(self.clear)
        menu.exec_(pos)

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
