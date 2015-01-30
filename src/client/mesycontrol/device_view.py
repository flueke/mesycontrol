#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtGui

import device_tableview

# Add a hackish way to fetch device memory before device widget display here:
# - initiate a fetch of missing device memory values
# - display a progress bar in the center tracking the progress of the fetch
# - once the fetch is done: hide the progress bar and instantiate and show the
#   real widget_class

class DeviceView(QtGui.QWidget):
    """Widget creating and showing either a specific device widget if one is
    available or the generic device table view.
    """
    def __init__(self, device, context, parent=None):
        super(DeviceView, self).__init__(parent)

        widget_class = context.get_device_widget_class(device.idc)

        if widget_class is not None:
            widget = widget_class(device, context)
        else:
            widget = device_tableview.DeviceTableWidget(device, context)

        layout = QtGui.QHBoxLayout()
        layout.addWidget(widget)
        self.setLayout(layout)
