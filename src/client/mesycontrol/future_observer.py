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

    def __init__(self, the_future, parent=None):
        super(FutureObserver, self).__init__(parent)
        self.future             = the_future
        self._progress_range    = self.future.progress_range()
        self._progress          = self.future.progress()
        self._progress_text     = self.future.progress_text()

        self.future.add_done_callback(self._future_done)
        self.future.add_progress_callback(self._future_progress)

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
