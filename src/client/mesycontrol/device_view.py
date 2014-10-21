#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtGui

import application_registry
import device_tableview

class DeviceView(QtGui.QWidget):
    def __init__(self, device, parent=None):
        super(DeviceView, self).__init__(parent)

        widget_class = application_registry.instance.get_device_widget_class(device.idc)

        if widget_class is not None:
            widget = widget_class(device)
        else:
            widget = device_tableview.DeviceTableWidget(device)

        layout = QtGui.QHBoxLayout()
        layout.addWidget(widget)
        self.setLayout(layout)
