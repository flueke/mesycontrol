#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtGui
from PyQt4 import uic
from mesycontrol import application_model

class DeviceWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(DeviceWidget, self).__init__(parent)
        uic.loadUi(application_model.instance.find_data_file('ui/device_widget.ui'), self)
