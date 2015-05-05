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

    def set_exception(self, exception):
        if self.done():
            raise FutureIsDone()

        self._exception = exception
        self._set_done()

    def add_done_callback(self, fn):
        if self.done():
            self._exec_callback(fn)
        else:
            self._callbacks.append(fn)

    def _set_done(self):
        self._done = True
        for cb in self._callbacks:
            self._exec_callback(cb)
        self._callbacks = list()

    def _exec_callback(self, cb):
        try:
            cb(self)
        except Exception as e:
            try:
                import logging
                logging.getLogger().warn("done_callback %s raised %s", cb, e)
            except ImportError:
                pass

    def then(self, fun):
        ret = Future()
        return ret


f1 = async1(args)
f2 = f1.then(async2)    # async2 will be called with f1.result()
f2.then(async3)         # async3 will be called with f2.result()

async1(args).then(async2).then(async3)
