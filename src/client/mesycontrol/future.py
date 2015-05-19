#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

class IncompleteFuture(Exception):
    pass

class FutureIsDone(Exception):
    pass

class Future(object):
    def __init__(self):
        self._done = False
        self._result = None
        self._exception = None
        self._callbacks = list()
        self._progress_callbacks = list()
        self._progress_min = 0
        self._progress_max = 100
        self._progress = 0
        self._progress_text = None

    def done(self):
        return self._done

    def result(self):
        if not self.done():
            raise IncompleteFuture()

        if self._exception is not None:
            raise self._exception

        return self._result

    def exception(self):
        if not self.done():
            raise IncompleteFuture()

        return self._exception

    def set_result(self, result):
        if self.done():
            raise FutureIsDone()

        self._result = result
        self._set_done()

        return self
    def set_exception(self, exception):
        if self.done():
            raise FutureIsDone()

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

    def set_progress_range(self, progress_min, progress_max):
        self._progress_min = progress_min
        self._progress_max = progress_max

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

    def _set_done(self):
        self._done = True
        for cb in self._callbacks:
            self._exec_callback(cb)
        self._callbacks = list()
        self._progress_callbacks = list()

    def _exec_callback(self, cb):
        try:
            cb(self)
        except Exception as e:
            try:
                import logging
                logging.getLogger().warn("callback %s raised %s", cb, e)
            except ImportError:
                pass

def all_done(*futures):
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

    return ret
