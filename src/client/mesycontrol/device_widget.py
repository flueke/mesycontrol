#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtGui

from device_tableview import DeviceTableModel, DeviceTableView

# TODO: refactor this to DeviceView (DeviceWidget should be the specific device
# widget)

class DeviceWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(DeviceWidget, self).__init__(parent)
        self.setLayout(QtGui.QHBoxLayout())

    def set_table_view(self, table_view):
        self.layout().addWidget(table_view)
        #table_view.setParent(self)

def factory(device):
    table_model   = DeviceTableModel(device)
    table_view    = DeviceTableView(table_model)
    #device_widget = application_registry.instance.make_device_widget(device)
    
    device_view = DeviceWidget()
    device_view.set_table_view(table_view)
    #device_view.set_device_widget(device_widget)
    return device_view
