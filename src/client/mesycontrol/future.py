#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import pyqtProperty
from qt import pyqtSignal
import logging

import util

class IncompleteFuture(RuntimeError):
    pass

class FutureIsDone(RuntimeError):
    pass

class Future(object):
    def __init__(self):
        self._done = False
        self._result = None
        self._exception = None
        self._exception_observed = False
        self._callbacks = list()
        self._progress_callbacks = list()
        self._progress_min = 0
        self._progress_max = 100
        self._progress = 0
        self._progress_text = None

    def __del__(self):
        if self._exception is not None and not self._exception_observed:
            logging.getLogger().error("Unobserved exception in Future: %s %s",
                    type(self._exception), self._exception)

    def done(self):
        return self._done

    def result(self):
        if not self.done():
            raise IncompleteFuture(self)

        if self._exception is not None:
            self._exception_observed = True
            raise self._exception

        return self._result

    def exception(self):
        if not self.done():
            raise IncompleteFuture(self)

        self._exception_observed = True
        return self._exception

    def set_result(self, result):
        if self.done():
            raise FutureIsDone(self)

        self._result = result
        self._set_done()

        return self

    def set_exception(self, exception):
        if self.done():
            raise FutureIsDone(self)

        self._exception = exception
        self._set_done()

        return self

    def progress(self):
        return self._progress

    def set_progress(self, progress):
        self._progress = progress
        for cb in self._progress_callbacks:
            self._exec_callback(cb)

    def progress_range(self):
        return (self._progress_min, self._progress_max)

    def progress_min(self):
        return self._progress_min

    def progress_max(self):
        return self._progress_max

    def set_progress_range(self, min_or_tuple, max_or_none=None):
        self._progress_min = min_or_tuple[0] if max_or_none is None else min_or_tuple
        self._progress_max = min_or_tuple[1] if max_or_none is None else max_or_none

    def progress_text(self):
        return self._progress_text

    def set_progress_text(self, txt):
        self._progress_text = txt
        for cb in self._progress_callbacks:
            self._exec_callback(cb)

    def add_done_callback(self, fn):
        if self.done():
            self._exec_callback(fn)
        else:
            self._callbacks.append(fn)

        return self

    def add_progress_callback(self, fn):
        if self.done():
            self._exec_callback(fn)
        else:
            self._progress_callbacks.append(fn)

        return self

    def _set_done(self):
        self._done = True
        for cb in self._callbacks:
            self._exec_callback(cb)
        self._callbacks = list()
        self._progress_callbacks = list()

    def _exec_callback(self, cb):
        try:
            cb(self)
        except Exception:
            logging.getLogger().exception("Callback %s raised", cb)

def all_done(*futures):
    """Returns a future that completes once all of the given futures complete.
    The returned futures result will be a list of futures in order of
    completion.
    """
    ret = Future()
    ret.set_progress_range(0, len(futures))
    done_futures = list()

    def on_future_done(f):
        done_futures.append(f)
        ret.set_progress(len(done_futures))
        if len(done_futures) == len(futures):
            ret.set_result(done_futures)

    for f in futures:
        f.add_done_callback(on_future_done)

    if len(futures) == 0:
        ret.set_result(list())

    return ret

def progress_forwarder(source, dest):
    def callback(f):
        dest.set_progress_range(source.progress_range())
        dest.set_progress_text(source.progress_text())

    source.add_progress_callback(callback)

class FutureObserver(QtCore.QObject):
    """Qt wrapper around a Future object using Qt signals to notify about state
    changes."""
    done                    = pyqtSignal()
    progress_range_changed  = pyqtSignal(int, int)
    progress_changed        = pyqtSignal(int)
    progress_text_changed   = pyqtSignal(str)

    def __init__(self, the_future=None, parent=None):
        super(FutureObserver, self).__init__(parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
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
        self.log.debug("Future %s is done", f)
        self.done.emit()

    def _future_progress(self, f):
        self.log.debug("Future %s progress changed r=%s p=%s t=%s",
                f, f.progress_range(), f.progress(), f.progress_text())

        if self._progress_range != f.progress_range():
            self._progress_range = f.progress_range()
            self.progress_range_changed.emit(*self._progress_range)

        if self._progress != f.progress():
            self._progress = f.progress()
            self.progress_changed.emit(self._progress)

        if self._progress_text != f.progress_text():
            self._progress_text = f.progress_text()
            self.progress_text_changed.emit(self._progress_text)

    future = pyqtProperty(object, get_future, set_future)
