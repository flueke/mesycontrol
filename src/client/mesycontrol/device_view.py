#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtGui

import application_registry
import device_tableview

class DeviceView(QtGui.QWidget):
    def __init__(self, device, parent=None):
        super(DeviceView, self).__init__(parent)
        self.setLayout(QtGui.QHBoxLayout())

        widget_class = application_registry.instance.get_device_widget_class(device.idc)

        table_view = device_tableview.DeviceTableView(
                device_tableview.DeviceTableModel(device))

        tab_widget = QtGui.QTabWidget(self)

        if widget_class is not None:
            tab_widget.addTab(widget_class(device), "Panel")

        tab_widget.addTab(table_view, "Table")
        self.layout().addWidget(tab_widget)
