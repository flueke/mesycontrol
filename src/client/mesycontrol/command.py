#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal
from functools import partial
import sys
import util

class CommandException(Exception): pass
class CommandStateException(CommandException): pass
class CommandInterrupted(CommandException): pass

class Command(QtCore.QObject):
    """Abstract base for runnable (and potentially asynchronous) commands."""

    #: Signals that the command was started.
    started          = pyqtSignal()

    #: Signals that the command has stopped either because it ran to completion
    #: or was manually stopped via a call to stop().
    stopped          = pyqtSignal()

    #: Used to signal that this commands progress has changed. Values are:
    #: (current, total) and (current). This is completely optional and has to be emitted by
    #: subclasses.
    progress_changed = pyqtSignal([int, int], [int])

    def __init__(self, parent=None):
        super(Command, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self._reset_state()

    def _reset_state(self):
        self._is_running   = False
        self._is_stopping  = False
        self._is_complete  = False
        self._exception    = None
        self._exception_tb = None

    def start(self):
        if self.is_running():
            raise CommandStateException("Command already started")

        try:
            self._reset_state()
            self.log.debug("%s: invoking start implementation", self)
            self._start()
            self.log.debug("%s: start implementation returned", self)
            self._is_running = True
            self.started.emit()
        except Exception as e:
            # Keep the current exception and traceback around to reraise them
            # in get_result().
            self.log.error("%s: start implementation raised %s (%s)", self, e, type(e))
            self._exception    = e
            self._exception_tb = sys.exc_info()[2]
            self._stopped(False)
            raise
        else:
            return self

    def stop(self):
        if self.is_running() and not self.is_stopping():
            self._is_stopping = True
            self._stop()

    def exec_(self):
        """Blocking execution of the command.
        Uses a local Qt eventloop to wait until the command stops. If the
        eventloops exec_() method returns an error CommandInterrupted will be
        raised (e.g. if QApplication.quit() is called from somewhere else).
        Returns a reference to self to allow chaining:
        my_result = MyCommand().exec_().get_result()
        """
        loop = QtCore.QEventLoop()
        self.stopped.connect(loop.quit)
        QtCore.QTimer.singleShot(0, self.start)
        self.log.debug("%s: Entering local event loop", self)
        if loop.exec_() < 0:
            raise CommandInterrupted()
        self.log.debug("%s: Local event loop returned", self)
        return self

    def __call__(self):
        """Shortcut for Command.exec_().get_result()"""
        return self.exec_().get_result()

    def _stopped(self, complete):
        """Must be called by subclasses to signal that they have stopped.
        The parameter 'complete' should be set to True if the command ran to
        completion, False otherwise.
        """
        self._is_running  = False
        self._is_stopping = False
        self._is_complete = complete
        self.stopped.emit()

    def is_running(self):  return self._is_running
    def is_stopping(self): return self._is_stopping
    def is_complete(self): return self._is_complete
    def is_ok(self):       return self.is_complete() and not self.has_failed()
    def has_failed(self):  return self._exception is not None or self._has_failed()

    def get_result(self):
        if self._exception is not None:
            # Re-raise an exception caught in start() using the original
            # traceback.
            raise self._exception, None, self._exception_tb
        return self._get_result()

    def get_exception(self):
        return self._exception

    def __len__(self): return 1
    def _start(self): raise NotImplementedError()
    def _stop(self): raise NotImplementedError()
    def _has_failed(self): raise NotImplementedError()
    def _get_result(self): raise NotImplementedError()

class CommandGroup(Command):
    """Abstract base for a group of commands."""
    def __init__(self, parent=None):
        super(CommandGroup, self).__init__(parent)
        self._commands = list()
    
    def add(self, cmd):
        if self.is_running():
            raise CommandStateException("Command group is running")
        cmd.setParent(self)
        self._commands.append(cmd)

    def remove(self, cmd):
        if self.is_running():
            raise CommandStateException("Command group is running")
        self._commands.remove(cmd)

    def clear(self):
        if self.is_running():
            raise CommandStateException("Command group is running")
        self._commands = list()

    def get_children(self):
        """Returns a copy of this commands list of children"""
        return list(self._commands)

    def _get_result(self):
        """Returns a list of child command results."""
        return [cmd.get_result() for cmd in self._commands]

    def _has_failed(self):
        return any(cmd.has_failed() for cmd in self._commands)

    def __len__(self):
        return len(self._commands)

class SequentialCommandGroup(CommandGroup):
    """Command group running its children in sequence."""

    def __init__(self, continue_on_error=False, parent=None):
        """If 'continue_on_error' is True all child commands will be run regardless of
        their results. Otherwise execution will stop after the first child command
        produced an error.
        """
        super(SequentialCommandGroup, self).__init__(parent)
        self.continue_on_error = continue_on_error
        self._current = None
        self.log = util.make_logging_source_adapter(__name__, self)

    def _start(self):
        self.log.debug("%s starting", self)
        self._start_next(enumerate(self._commands))

    def _start_next(self, cmd_iter):
        try:
            idx, cmd = cmd_iter.next()
        except StopIteration:
            self._current = None
            self._stopped(all(cmd.is_complete() for cmd in self._commands))
        else:
            self._current = cmd
            cmd.stopped.connect(partial(self._child_stopped, cmd=cmd, idx=idx, cmd_iter=cmd_iter))
            self.log.debug("Starting subcommand %d/%d: %s", idx+1, len(self), cmd)
            try:
                cmd.start()
            except Exception as e:
                self._exception    = e
                self._exception_tb = sys.exc_info()[2]
                self._stopped(False)
                raise

    def _stop(self):
        if self._current is not None:
            # Stop the child. Execution will continue in _child_stopped() once
            # the child actually has stopped.
            self._current.stop()
        else:
            # Immediately signal stopping completed to the parent
            self._stopped(all(cmd.is_complete() for cmd in self._commands))

    def _child_stopped(self, cmd, idx, cmd_iter):
        self._current = None

        if self.is_stopping() or (cmd.has_failed() and not self.continue_on_error):
            self._stopped(all(cmd.is_complete() for cmd in self._commands))
        else:
            self.progress_changed[int, int].emit(idx+1, len(self))
            self.progress_changed[int].emit(idx+1)
            self._start_next(cmd_iter)

    def get_first_failed(self):
        for cmd in self._commands:
            if cmd.has_failed(): return cmd
        return None

class ParallelCommandGroup(CommandGroup):
    """Command group running all its children in parallel."""

    def __init__(self, parent=None):
        super(ParallelCommandGroup, self).__init__(parent)

    def _start(self):
        self._num_stopped = 0
        for cmd in self._commands:
            cmd.stopped.connect(partial(self._child_stopped, cmd=cmd))
            cmd.start()

    def _stop(self):
        for cmd in filter(lambda c: c.is_running(), self._commands):
            cmd.stop()

    def _child_stopped(self, cmd):
        self._num_stopped += 1
        self.progress_changed[int, int].emit(self._num_stopped, len(self))
        self.progress_changed[int].emit(self._num_stopped)

        if self._num_stopped == len(self):
            self._stopped(all(cmd.is_complete() for cmd in self._commands))

class Sleep(Command):
    def __init__(self, duration_ms, parent=None):
        super(Sleep, self).__init__(parent)
        self._duration_ms = duration_ms
        self._timer = QtCore.QTimer(self, timeout=partial(self._stopped, True))
        self._timer.setSingleShot(True)

    def _start(self):
        self._timer.start(self._duration_ms)

    def _stop(self):
        self._timer.stop()
        self._stopped(True)

    def _get_result(self): return True

    def __str__(self):
        return "Sleep(%dms)" % self._duration_ms

class Callable(Command):
    def __init__(self, the_callable, parent=None):
        super(Callable, self).__init__(parent)
        self._callable = the_callable
        self._result   = None

    def _start(self):
        self._result = self._callable()
        self._stopped(True)

    def _stop(self):
        pass

    def _get_result(self):
        return self._result

    def _has_failed(self):
        return False

    def __str__(self):
        return "Callable(%s)" % self._callable
