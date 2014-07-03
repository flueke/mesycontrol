#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtGui
from PyQt4 import uic
import application_model

class ChannelWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(ChannelWidget, self).__init__(parent)
        uic.loadUi(application_model.instance.find_data_file('ui/mhv4_channel.ui'), self)

class MHV4Widget(QtGui.QWidget):
    def __init__(self, model, parent=None):
        super(MHV4Widget, self).__init__(parent)
