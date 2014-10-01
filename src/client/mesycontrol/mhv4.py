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

def get_device_info():
    return (MHV4.idcs, MHV4)

def get_widget_info():
    return (MHV4.idcs, MHV4Widget)

class Polarity(object):
    negative = 0
    positive = 1

class MHV4(app_model.Device):
    num_channels  = 4
    idcs          = (17, 27)

    actual_voltage_changed = pyqtSignal(int, int)     #: channel, raw value
    target_voltage_changed = pyqtSignal(int, int)     #: channel, raw value
    voltage_limit_changed  = pyqtSignal(int, int)     #: channel, raw value
    actual_current_changed = pyqtSignal(int, int)     #: channel, raw value
    current_limit_changed  = pyqtSignal(int, int)     #: channel, raw value
    channel_state_changed  = pyqtSignal(int, bool)      #: channel, value
    polarity_changed       = pyqtSignal(int, Polarity)  #: channel, Polarity

    def __init__(self, device_model=None, device_config=None, device_profile=None, parent=None):
        super(MHV4, self).__init__(device_model=device_model, device_config=device_config,
                device_profile=device_profile, parent=parent)

        self.log = util.make_logging_source_adapter(__name__, self)

    def get_actual_voltage(self, channel, unit_label='raw'):
        return self.get_parameter_by_name('channel%d_voltage_read' % channel, unit_label)

    def get_target_voltage(self, channel, unit_label='raw'):
        return self.get_parameter_by_name('channel%d_voltage_write' % channel, unit_label)

    def set_target_voltage(self, channel, voltage, unit_label='raw', response_handler=None):
        return self.set_parameter_by_name('channel%d_voltage_write' % channel, voltage, unit_label, response_handler)

    def set_channel_enabled(self, channel, on_off, response_handler=None):
        return self.set_parameter_by_name('channel%d_enable_write' % channel, 1 if on_off else 0, response_handler)

    def enable_all_channels(self):
        for i in range(MHV4.num_channels):
            self.set_channel_enabled(i+1, True)

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
