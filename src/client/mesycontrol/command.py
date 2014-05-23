#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal
from functools import partial

class CommandException(Exception): pass
class CommandStateException(CommandException): pass
class CommandInterrupted(CommandException): pass

class Command(QtCore.QObject):
    started  = pyqtSignal()
    stopped  = pyqtSignal()
    progress_changed = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super(Command, self).__init__(parent)
        self._is_running  = False
        self._is_stopping = False
        self._exception = None

    def start(self):
        if self.is_running():
            raise CommandStateException("Command already started")

        try:
            self._start()
            self._is_running  = True
            self._is_stopping = False
            self.started.emit()
        except Exception as e:
            self._exception = e
            self._stopped()

    def stop(self):
        if not self.is_running():
            raise CommandStateException("Command not running")

        if self.is_stopping(): return

        self._is_stopping = True
        self._stop()

    def exec_(self):
        loop = QtCore.QEventLoop()
        self.stopped.connect(loop.quit)
        QtCore.QTimer.singleShot(0, self.start)
        if loop.exec_() < 0:
            raise CommandInterrupted()
        return self

    def _stopped(self):
        self._is_running  = False
        self._is_stopping = False
        self.stopped.emit()

    def is_running(self): return self._is_running
    def is_stopping(self): return self._is_stopping

    def get_result(self):
        if self._exception is not None:
            raise self._exception
        return self._get_result()

    def has_failed(self): return self._exception is not None
    def __len__(self): return 1
    def _start(self): raise NotImplemented()
    def _stop(self): raise NotImplemented()
    def _get_result(self): raise NotImplemented()

class CommandGroup(Command):
    def __init__(self, parent=None):
        super(CommandGroup, self).__init__(parent)
        self._commands = list()
    
    def add(self, cmd):
        if self.is_running():
            raise CommandStateException("Command group is running")
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
        """Returns a copy of this commands child list"""
        return list(self._commands)

    def _get_result(self):
        """Returns a list of child command results."""
        return [cmd.get_result() for cmd in self._commands]

    def has_failed(self):
        return (super(CommandGroup, self).has_failed() or
                any(cmd.has_failed() for cmd in self._commands))

    def __len__(self):
        return len(self._commands)

class SequentialCommandGroup(CommandGroup):
    def __init__(self, continue_on_error=False, parent=None):
        super(SequentialCommandGroup, self).__init__(parent)
        self.continue_on_error = continue_on_error
        self._current = None

    def _start(self):
        cmd_iter = enumerate(self._commands)
        self._start_next(cmd_iter)

    def _stop(self):
        if self._current is not None and self._current.is_running():
            self._current.stop()
        else:
            # Immediately signal stopping completed to the parent
            self._stopped()

    def _start_next(self, cmd_iter):
        try:
            idx, cmd = cmd_iter.next()
            self._current = cmd
            cmd.stopped.connect(partial(self._child_stopped, cmd=cmd, idx=idx, cmd_iter=cmd_iter))
            cmd.start()
        except StopIteration:
            self._current = None
            self._stopped()

    def _child_stopped(self, cmd, idx, cmd_iter):
        self._current = None

        if self.is_stopping() or (cmd.has_failed() and not self.continue_on_error):
            self._stopped()
        else:
            self.progress_changed.emit(idx+1, len(self))
            self._start_next(cmd_iter)

    def get_first_failed(self):
        for cmd in self._commands:
            if cmd.has_failed(): return cmd
        return None

class ParallelCommandGroup(CommandGroup):
    def __init__(self, parent=None):
        super(ParallelCommandGroup, self).__init__(parent)

    def _start(self):
        self._num_completed = 0
        for cmd in self._commands:
            cmd.stopped.connect(partial(self._child_stopped, cmd=cmd))
            cmd.start()

    def _stop(self):
        for cmd in filter(lambda c: c.is_running(), self._commands):
            cmd.stop()

    def _child_stopped(self, cmd):
        self._num_completed += 1
        self.progress_changed.emit(self._num_completed, len(self))

        if self._num_completed == len(self):
            self._stopped()

class Sleep(Command):
    def __init__(self, duration_ms, parent=None):
        super(Sleep, self).__init__(parent)
        self._duration_ms = duration_ms
        self._timer = QtCore.QTimer(self, timeout=self._stopped)
        self._timer.setSingleShot(True)

    def _start(self):
        self._timer.start(self._duration_ms)

    def _stop(self):
        self._timer.stop()

    def _get_result(self): return True
