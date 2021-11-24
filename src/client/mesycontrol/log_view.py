#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2016 mesytec GmbH & Co. KG <info@mesytec.com>
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

__author__ = 'Florian Lüke'
__email__  = 'f.lueke@mesytec.com'

from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui
from mesycontrol.qt import QtWidgets
import logging
import sys
import time
import traceback

import mesycontrol.util as util

class LogView(QtWidgets.QTextEdit):
    def __init__(self, max_lines=10000, line_wrap=QtWidgets.QTextEdit.WidgetWidth, parent=None):
        super(LogView, self).__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(max_lines)
        self.setLineWrapMode(line_wrap)

        self.err_fmt = logging.Formatter(
                fmt='%(asctime)s %(name)s: %(message)s',
                datefmt='%H:%M:%S')

        self.fmt = logging.Formatter(
                fmt='%(asctime)s: %(message)s',
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
                    self.append(self.err_fmt.format(log_record), prepend_time=False)
                else:
                    self.append(self.fmt.format(log_record), prepend_time=False)
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

    button = QtWidgets.QPushButton("Log!", clicked=on_button_clicked)
    button.show()

    sys.exit(qapp.exec_())
