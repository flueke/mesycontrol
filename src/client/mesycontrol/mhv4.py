#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import uic
import weakref
import application_registry

class MHV4(QtCore.QObject):
    def __init__(self, device, parent=None):
        self.device = weakref.ref(device)

class ChannelWidget(QtGui.QWidget):
    def __init__(self, mhv4, channel, parent=None):
        super(ChannelWidget, self).__init__(parent)
        uic.loadUi(application_registry.instance.find_data_file('ui/mhv4_channel.ui'), self)
        self.mhv4    = weakref.ref(mhv4)
        self.channel = channel

class MHV4Widget(QtGui.QWidget):
    def __init__(self, device, parent=None):
        super(MHV4Widget, self).__init__(parent)

        self.device = device

        channel_layout = QtGui.QHBoxLayout()
        channel_layout.setContentsMargins(4, 4, 4, 4)

        for i in range(4):
            groupbox        = QtGui.QGroupBox("Channel %d" % (i+1), self)
            channel_widget  = ChannelWidget(device, i, groupbox)
            groupbox_layout = QtGui.QHBoxLayout(groupbox)
            groupbox_layout.setContentsMargins(4, 4, 4, 4)
            groupbox_layout.addWidget(channel_widget)
            channel_layout.addWidget(groupbox)

        vbox = QtGui.QVBoxLayout(self)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.addItem(channel_layout)

if __name__ == "__main__":
    import sys
    import hw_model
    import app_model

    qapp = QtGui.QApplication(sys.argv)

    application_registry.instance = application_registry.ApplicationRegistry(
            sys.executable if getattr(sys, 'frozen', False) else __file__)

    mhv4_model  = hw_model.DeviceModel(bus=0, address=0, idc=17, rc=True)
    mhv4        = app_model.Device(device_model=mhv4_model)
    mhv4_widget = MHV4Widget(mhv4)
    mhv4_widget.show()
    sys.exit(qapp.exec_())
