#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import pyqtSignal

class FutureObserver(QtCore.QObject):
    done                    = pyqtSignal()
    progress_range_changed  = pyqtSignal(int, int)
    progress_changed        = pyqtSignal(int)
    progress_text_changed   = pyqtSignal(str)

    def __init__(self, the_future=None, parent=None):
        super(FutureObserver, self).__init__(parent)
        self.future = the_future

    def get_future(self):
        return self._future

    def set_future(self, the_future):
        self._future = the_future

        if self.future is not None:
            self._progress_range    = self.future.progress_range()
            self._progress          = self.future.progress()
            self._progress_text     = self.future.progress_text()
            self.future.add_done_callback(self._future_done)
            self.future.add_progress_callback(self._future_progress)
        else:
            self._progress_range    = (0, 0)
            self._progress          = 0
            self._progress_text     = str()

    def _future_done(self, f):
        self.done.emit()

    def _future_progress(self, f):
        if self._progress_range != f.progress_range():
            self._progress_range = f.progress_range
            self.progress_range_changed.emit(*self._progress_range)

        if self._progress != f.progress():
            self._progress = f.progress
            self.progress_changed.emit(self._progress)

        if self._progress_text != f.progress_text():
            self._progress_text = f.progress_text
            self.progress_text_changed.emit(self._progress_text)
