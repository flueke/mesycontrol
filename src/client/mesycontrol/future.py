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

    def set_exception(self, exception):
        if self.done():
            raise FutureIsDone()

        self._exception = exception
        self._set_done()

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


def on_f1_done(f1):
    print "f1 done:", f1.result()

f1 = Future()
f1.add_done_callback(on_f1_done)
f1.set_result("foobar")


f1 = Future()
f2 = Future()
f3 = Future()

def on_all_done(f):
    print "all futures done"
    for fu in f.result():
        print fu, fu.result() if fu.exception() is None else repr(fu.exception())

def on_progress_changed(f):
    print "progress changed:", f.progress()

f_all = all_done(f1, f2, f3)
f_all.add_done_callback(on_all_done)
f_all.add_progress_callback(on_progress_changed)

f2.set_result("bar")
f3.set_exception(RuntimeError("hello"))
f1.set_result("foo")


class MSCF:
    def get_version(self):
        ret = Future()

        f_reg1 = self.get_parameter(254)
        f_reg2 = self.get_parameter(255)

        def on_regs_available(f):
            try:
                version = f_reg1.result() + f_reg2.result()
                ret.set_result(version)
            except Exception as e:
                ret.set_exception(e)

        all_done(f_reg1, f_reg2).add_done_callback(on_regs_available)
        
        return ret

    def get_parameter(self, address):
        print "get_parameter", address
        ret = Future()
        ret.set_result(address)
        return ret

mscf = MSCF()
def print_version(future):
    print "version:", future.result()

mscf.get_version().add_done_callback(print_version)
