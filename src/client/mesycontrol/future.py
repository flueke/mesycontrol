#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2021 mesytec GmbH & Co. KG <info@mesytec.com>
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
from mesycontrol.qt import QtWidgets
from mesycontrol.qt import Property
from mesycontrol.qt import Signal

from functools import wraps
import traceback
import sys

import mesycontrol.util as util

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
        self._name = str()

        self.log = util.make_logging_source_adapter(__name__, self)

    def __del__(self):
        if self._exception is not None and not self._exception_observed:
            self.log.error("Unobserved exception in Future: %s %s",
                    type(self._exception), self._exception)
        self.log.log(5, f"future being destroyed! {self=}, {self.done()=}")

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

    def add_done_callback(self, fn, unique=True):
        assert fn is not None

        if self.done():
            self._exec_callback(fn)
        elif not unique or (fn not in self._callbacks):
            self._callbacks.append(fn)

        return self

    def add_progress_callback(self, fn, unique=True):
        assert fn is not None

        if self.done():
            self._exec_callback(fn)
        elif not unique or (fn not in self._progress_callbacks):
            self._progress_callbacks.append(fn)

        return self

    def get_name(self):
        return self._name

    def set_name(self, name):
        self._name = name

    name = property(get_name, set_name)

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

        exception.traceback_lines = traceback.format_exception(*sys.exc_info())

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
            self.log.debug("%s done: exception: %s", self, self.exception())
        elif self.done():
            self.log.debug("%s done: resultType: %s, result: %s", self, type(self.result()), self.result())
        else:
            self.log.debug("%s NOT done!", self)

        for cb in self._callbacks:
            self._exec_callback(cb)

        self._callbacks = list()
        self._progress_callbacks = list()

    def _exec_callback(self, cb):
        try:
            cb(self)
        except Exception:
            self.log.exception("Callback %s raised", cb)

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
    done                    = Signal()
    cancelled               = Signal()
    progress_range_changed  = Signal(int, int)
    progress_changed        = Signal(int)
    progress_text_changed   = Signal(str)

    def __init__(self, the_future=None, parent=None):
        super(FutureObserver, self).__init__(parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self.future = the_future
        self.log.debug(f"FutureObserver created with future={self.future}")

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

    future = Property(object, get_future, set_future)

    def result(self):
        return self.future.result()

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
            pd = QtWidgets.QProgressDialog()

            if not cancelable:
                pd.setCancelButton(None)

            fo.progress_range_changed.connect(pd.setRange)
            fo.progress_changed.connect(pd.setValue)
            fo.progress_text_changed.connect(pd.setLabelText)
            fo.done.connect(pd.close)

            pd.exec_()

        return wrapper

    return deco

# Waits for the result of the given future to be available and returns the
# result.
def get_future_result(theFuture):
    observer = FutureObserver(theFuture)
    if not observer.future.done():
        util.wait_for_signal(signal=observer.done)
    return observer.result()

if __name__ == "__main__":
    ret = Future()

    @set_result_on(ret)
    def my_func():
        return 42

    my_func()
    print(ret.result())

    # ==================

    ret = Future()

    @set_result_on(ret)
    def my_func():
        raise ValueError(42)

    my_func()
    try:
        print(ret.result())
    except Exception as e:
        print(type(e), e)

    # ==================
    ret = Future()

    @set_exception_on(ret)
    def my_func():
        return 42

    my_func()
    try:
        print(ret.result())
    except Exception as e:
        print(type(e), e)

    # ==================
    ret = Future()

    @set_exception_on(ret)
    def my_func():
        raise ValueError(42)

    my_func()
    try:
        print(ret.result())
    except Exception as e:
        print(type(e), e)
