"""
ActiveState:
http://code.activestate.com/recipes/578634-pyqt-pyside-thread-safe-callbacks-main-loop-integr/

ref and proxy classes are based on:
    http://code.activestate.com/recipes/81253/#c5

Modified proxy to support a quiet concept for callbacks that can 
simply pass if they were not valid, instead of raising an exception.

Callback event dispatch based on:
    http://code.activestate.com/recipes/578299-pyqt-pyside-thread-safe-global-queue-main-loop-int/

Modified to simplify the process, by removing the Queue and threaded dispatcher,
and just using a more developed Event object that posts directly to the event loop.

"""

import weakref
import types

from functools import partial
from multiprocessing.pool import ThreadPool

__all__ = [
    "ref",
    "proxy",
    "CallbackEvent",
    "CallbackThreadPool",
]

class ref(object):
    """
    A weak method implementation
    """
    def __init__(self, method):
        try:

            if method.im_self is not None:
                # bound method
                self._obj = weakref.ref(method.im_self)

            else:
                # unbound method
                self._obj = None

            self._func = method.im_func
            self._class = method.im_class

        except AttributeError:
            # not a method
            self._obj = None
            self._func = method
            self._class = None
 
    def __call__(self):
        """
        Return a new bound-method like the original, or the
        original function if refers just to a function or unbound
        method.
        Returns None if the original object doesn't exist
        """
        if self.is_dead():
            return None

        if self._obj is not None:
            # we have an instance: return a bound method
            return types.MethodType(self._func, self._obj(), self._class)
        
        else:
            # we don't have an instance: return just the function
            return self._func
  
    def is_dead(self):
        """
        Returns True if the referenced callable was a bound method and
        the instance no longer exists. Otherwise, return False.
        """
        return self._obj is not None and self._obj() is None
 
    def __eq__(self, other):
        try:
            return type(self) is type(other) and self() == other()
        except:
            return False
  
    def __ne__(self, other):
        return not self == other
 
 
#
# The modified proxy class, adding a quiet option
#
class proxy(ref):
    """
    Exactly like ref, but calling it will cause the referent method to
    be called with the same arguments. If the referent's object no longer lives,
    ReferenceError is raised.

    If quiet is True, then a ReferenceError is not raise and the callback 
    silently fails if it is no longer valid. 
    """
 
    def __init__(self, method, quiet=False):
        super(proxy, self).__init__(method)
        self._quiet = quiet
 
    def __call__(self, *args, **kwargs):
        func = ref.__call__(self)

        if func is None:
            if self._quiet:
                return
            else:
                raise ReferenceError('object is dead')

        else:
            return func(*args, **kwargs)
  
    def __eq__(self, other):
        try:
            func1 = ref.__call__(self)
            func2 = ref.__call__(other)
            return type(self) == type(other) and func1 == func2

        except:
            return False


#
# PyQt4 / PySide Thread-Safe Callback Dispatch
#
try:
    from PySide import QtGui, QtCore
except ImportError:
    from PyQt4 import QtGui, QtCore


class _Invoker(QtCore.QObject):

    def customEvent(self, e):
        e.callback()


class CallbackEvent(QtCore.QEvent):
    """
    A custom QEvent that contains a callback reference

    Also provides class methods for conveniently executing 
    arbitrary callback, to be dispatched to the event loop.
    """
    EVENT_TYPE = QtCore.QEvent.Type(QtCore.QEvent.registerEventType())

    __invoker = _Invoker()

    def __init__(self, func, *args, **kwargs):
        super(CallbackEvent, self).__init__(self.EVENT_TYPE)
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def callback(self):
        """
        Convenience method to run the callable. 

        Equivalent to:  
            self.func(*self.args, **self.kwargs)
        """
        self.func(*self.args, **self.kwargs)

    @classmethod
    def post(cls, func, *args, **kwargs):
        """
        Post a callable to run in the main thread
        """
        cls.post_to(cls.__invoker, func, *args, **kwargs)

    @classmethod
    def post_to(cls, receiver, func, *args, **kwargs):
        """
        Post a callable to be delivered to a specific
        receiver as a CallbackEvent. 

        It is the responsibility of this receiver to 
        handle the event and choose to call the callback.
        """
        # We can create a weak proxy reference to the
        # callback so that if the object associated with
        # a bound method is deleted, it won't call a dead method
        if not isinstance(func, proxy):
            reference = proxy(func, quiet=True)
        else:
            reference = func

        event = cls(reference, *args, **kwargs)

        # post the event to the given receiver
        QtGui.QApplication.postEvent(receiver, event)


class CallbackThreadPool(ThreadPool):
    """
    Simple wrapper around ThreadPool to wrap callbacks in a weakref 
    that get posted as CallbackEvents in the main thread.
    """
    def apply_async(self, fn, args=None, kwargs=None, callback=None):
        proxyCbk = self._async_helper(callback)
        args = args or tuple
        kwargs = kwargs or {}
        return super(CallbackThreadPool, self).apply_async(fn, args, kwargs, proxyCbk)

    def map_async(self, fn, iterable, chunk=None, callback=None):
        proxyCbk = self._async_helper(callback)
        return super(CallbackThreadPool, self).map_async(fn, iterable, chunk, callback)

    @staticmethod
    def _async_helper(callback):
        if callback:
            proxyCbk = partial(CallbackEvent.post, proxy(callback, quiet=True))
        else:
            proxyCbk = None

        return proxyCbk



if __name__ == "__main__":

    def the_callback(*args, **kwargs):
        print "the_callback invoked with", args, kwargs
        import traceback
        traceback.print_stack()

    def on_button_clicked():
        CallbackEvent.post(the_callback, "hello", "world", foo="foo", bar="bar")

    app = QtGui.QApplication([])

    button = QtGui.QPushButton("invoke callback", clicked=on_button_clicked)
    button.show()

    app.exec_()

    the_callback("hello", "world", foo="foo", bar="bar")
