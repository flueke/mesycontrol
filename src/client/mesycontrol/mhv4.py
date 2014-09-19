#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtGui
from PyQt4 import uic
from PyQt4.QtCore import pyqtSignal
import weakref

import application_registry
import app_model
import util

class MHV4_800V(app_model.Device):
    class Polarity:
        negative = 0
        positive = 1

    num_channels  = 4
    idc           = 27

    actual_voltage_changed = pyqtSignal(int, float)     #: channel, value
    target_voltage_changed = pyqtSignal(int, float)     #: channel, value
    voltage_limit_changed  = pyqtSignal(int, float)     #: channel, value
    actual_current_changed = pyqtSignal(int, float)     #: channel, value
    current_limit_changed  = pyqtSignal(int, float)     #: channel, value
    channel_state_changed  = pyqtSignal(int, bool)      #: channel, value
    polarity_changed       = pyqtSignal(int, int)       #: channel, Polarity

    def __init__(self, device_model=None, device_config=None, device_description=None, parent=None):
        if device_model is not None and device_model.idc != MHV4_800V.idc:
            raise RuntimeError("MHV4_800V: expected device_model.idc=%d, got %d"
                    % (MHV4_800V.idc, device_model.idc))

        if device_config is not None and device_config.idc != MHV4_800V.idc:
            raise RuntimeError("MHV4_800V: expected device_config.idc=%d, got %d"
                    % (MHV4_800V.idc, device_config.idc))

        if device_description is not None and device_description.idc != MHV4_800V.idc:
            raise RuntimeError("MHV4_800V: expected device_description.idc=%d, got %d"
                    % (MHV4_800V.idc, device_description.idc))
        elif device_description is None:
            device_description = application_registry.instance.get_device_description_by_idc(MHV4_800V.idc)

        super(MHV4_800V, self).__init__(device_model=device_model, device_config=device_config,
                device_description=device_description, parent=parent)

        self.log = util.make_logging_source_adapter(__name__, self)

    def get_actual_voltage(self, channel):
        pass

    def get_target_voltage(self, channel):
        pass

    def set_target_voltage(self, channel, voltage):
        pass


    def get_voltage_limit(self, channel):
        pass

    def set_voltage_limit(self, channel, voltage):
        pass


    def get_actual_current(self, channel):
        pass

    def get_current_limit(self, channel):
        pass

    def set_current_limit(self, channel, current):
        pass


    def get_channel_state(self, channel):
        pass

    def set_channel_state(self, channel, on_off):
        pass


    def get_polarity(self, channel):
        pass

    def set_polarity(self, channel, polarity):
        pass


class ChannelWidget(QtGui.QWidget):
    def __init__(self, mhv4, channel, parent=None):
        super(ChannelWidget, self).__init__(parent)
        uic.loadUi(application_registry.instance.find_data_file('mesycontrol/ui/mhv4_channel.ui'), self)
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

    application_registry.instance = application_registry.ApplicationRegistry(__file__)

    mhv4_model  = hw_model.DeviceModel(bus=0, address=0, idc=17, rc=True)
    mhv4        = app_model.Device(device_model=mhv4_model)
    mhv4_widget = MHV4Widget(mhv4)
    mhv4_widget.show()
    sys.exit(qapp.exec_())
