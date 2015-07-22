#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import QtGui
from qt import pyqtProperty
from qt import pyqtSignal

from functools import wraps
import logging

import util

class IncompleteFuture(RuntimeError):
    pass

class FutureIsDone(RuntimeError):
    pass

class FutureIsRunning(RuntimeError):
    pass

class CancelledError(RuntimeError):
    pass

class Future(object):
    def __init__(self):
        self._done = False
        self._result = None
        self._exception = None
        self._exception_observed = False
        self._running = False
        self._cancelled = False
        self._callbacks = list()
        self._progress_callbacks = list()
        self._progress_min = 0
        self._progress_max = 100
        self._progress = 0
        self._progress_text = str()

        self.log = util.make_logging_source_adapter(__name__, self)

    def __del__(self):
        if self._exception is not None and not self._exception_observed:
            logging.getLogger().error("Unobserved exception in Future: %s %s",
                    type(self._exception), self._exception)

    # ===== Client functionality =====
    def done(self):
        return self._done

    def result(self):
        if not self.done():
            raise IncompleteFuture(self)

        if self.cancelled():
            raise CancelledError()

        if self._exception is not None:
            self._exception_observed = True
            raise self._exception

        return self._result

    def exception(self):
        if not self.done():
            raise IncompleteFuture(self)

        if self.cancelled():
            raise CancelledError()

        self._exception_observed = True
        return self._exception

    def cancel(self):
        if self.done() or self.running():
            return False

        self.log.info("%s: canceled", self)

        self._cancelled = True
        self._set_done()
        return True

    def cancelled(self):
        return self._cancelled

    def running(self):
        return self._running

    def progress(self):
        return self._progress

    def progress_range(self):
        return (self._progress_min, self._progress_max)

    def progress_min(self):
        return self._progress_min

    def progress_max(self):
        return self._progress_max

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

    # ===== Executor functionality =====
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

    def set_running_or_notify_cancel(self):
        """If the method returns False then the Future was cancelled. Otherwise
        the Future will be put in running state and True is returned."""

        if self.running():
            raise FutureIsRunning()

        if self._result is not None or self._exception is not None:
            raise FutureIsDone()

        if self.cancelled():
            return False

        self._running = True
        return True

    def set_progress(self, progress):
        self._progress = progress

        for cb in self._progress_callbacks:
            self._exec_callback(cb)

    def set_progress_range(self, min_or_tuple, max_or_none=None):
        self._progress_min = min_or_tuple[0] if max_or_none is None else min_or_tuple
        self._progress_max = min_or_tuple[1] if max_or_none is None else max_or_none

    def progress_text(self):
        return self._progress_text

    def set_progress_text(self, txt):
        self._progress_text = txt

        for cb in self._progress_callbacks:
            self._exec_callback(cb)

    def _set_done(self):
        if self._done:
            raise FutureIsDone()

        self._done = True
        self._running = False

        if self.cancelled():
            self.log.debug("%s done: canceled", self)
        elif self.exception() is not None:
            self.log.debug("%s done: %s", self, self.exception())
        else:
            self.log.debug("%s done: %s", self, self.result())

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
        dest.set_progress(source.progress())
        dest.set_progress_text(source.progress_text())

    source.add_progress_callback(callback)

class FutureObserver(QtCore.QObject):
    """Qt wrapper around a Future object using Qt signals to notify about state
    changes."""
    done                    = pyqtSignal()
    cancelled               = pyqtSignal()
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

        self.progress_range_changed.emit(*self._progress_range)
        self.progress_changed.emit(self._progress)
        self.progress_text_changed.emit(self._progress_text)

    def _future_done(self, f):
        self.log.debug("Future %s is done", f)
        if f.cancelled():
            self.cancelled.emit()
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

def set_result_on(result_future):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                result_future.set_result(f(*args, **kwargs))
            except Exception as e:
                result_future.set_exception(e)
        return wrapper
    return deco

def set_exception_on(result_future):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                f(*args, **kwargs)
            except Exception as e:
                result_future.set_exception(e)
        return wrapper
    return deco

def future_progress_dialog(cancelable=True):
    def deco(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            f  = func(*args, **kwargs)

            if f.done():
                return

            fo = FutureObserver(the_future=f)
            pd = QtGui.QProgressDialog()

            if not cancelable:
                pd.setCancelButton(None)

            fo.progress_range_changed.connect(pd.setRange)
            fo.progress_changed.connect(pd.setValue)
            fo.progress_text_changed.connect(pd.setLabelText)
            fo.done.connect(pd.close)

            pd.exec_()

        return wrapper

    return deco


if __name__ == "__main__":
    ret = Future()

    @set_result_on(ret)
    def my_func():
        return 42

    my_func()
    print ret.result()

    # ==================

    ret = Future()

    @set_result_on(ret)
    def my_func():
        raise ValueError(42)

    my_func()
    try:
        print ret.result()
    except Exception as e:
        print type(e), e

    # ==================
    ret = Future()

    @set_exception_on(ret)
    def my_func():
        return 42

    my_func()
    try:
        print ret.result()
    except Exception as e:
        print type(e), e

    # ==================
    ret = Future()

    @set_exception_on(ret)
    def my_func():
        raise ValueError(42)

    my_func()
    try:
        print ret.result()
    except Exception as e:
        print type(e), e
