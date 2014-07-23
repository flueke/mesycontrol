#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import uic
import weakref
import application_model

class MHV4(QtCore.QObject):
    def __init__(self, device, parent=None):
        self.device = weakref.ref(device)

class ChannelWidget(QtGui.QWidget):
    def __init__(self, mhv4, channel, parent=None):
        super(ChannelWidget, self).__init__(parent)
        uic.loadUi(application_model.instance.find_data_file('ui/mhv4_channel.ui'), self)
        self.mhv4    = weakref.ref(mhv4)
        self.channel = channel

class MHV4Widget(QtGui.QWidget):
    def __init__(self, device, parent=None):
        super(MHV4Widget, self).__init__(parent)
