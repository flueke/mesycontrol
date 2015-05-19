#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal

class PyObject(object):
    the_signal = pyqtSignal()

    def the_method(self):
        print self

    def __del__(self):
        print "del", self

class QtObject(QtCore.QObject):
    the_signal = pyqtSignal()

    def __init__(self, parent=None):
        super(QtObject, self).__init__(parent)

    def the_method(self):
        print self

    def __del__(self):
        print "del", self

py_obj = PyObject()
qt_obj = QtObject()
