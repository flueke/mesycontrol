#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtGui
from PyQt4 import uic
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import pyqtSlot
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
    idcs          = (27,)

    actual_voltage_changed = pyqtSignal(int, int)       #: channel, raw value
    target_voltage_changed = pyqtSignal(int, int)       #: channel, raw value
    voltage_limit_changed  = pyqtSignal(int, int)       #: channel, raw value
    actual_current_changed = pyqtSignal(int, int)       #: channel, raw value
    current_limit_changed  = pyqtSignal(int, int)       #: channel, raw value
    channel_state_changed  = pyqtSignal(int, bool)      #: channel, value
    polarity_changed       = pyqtSignal(int, int)       #: channel, Polarity.(negative|positive)

    def __init__(self, device_model=None, device_config=None, device_profile=None, parent=None):
        super(MHV4, self).__init__(device_model=device_model, device_config=device_config,
                device_profile=device_profile, parent=parent)

        self.log = util.make_logging_source_adapter(__name__, self)

        self.parameter_changed[object, int, int].connect(self._on_parameter_changed)

    def _on_parameter_changed(self, param, old_value, new_value):
        p = self.profile

        if p['channel0_voltage_write'] <= param <= p['channel3_voltage_write']:
            self.target_voltage_changed.emit(param.index, new_value)

        elif p['channel0_voltage_read'] <= param <= p['channel3_voltage_read']:
            self.actual_voltage_changed.emit(param.index, new_value)

        elif p['channel0_enable_read'] <= param <= p['channel3_enable_read']:
            self.channel_state_changed.emit(param.index, new_value)

        elif p['channel0_current_limit_read'] <= param <= p['channel3_current_limit_read']:
            self.current_limit_changed.emit(param.index, new_value)

        elif p['channel0_voltage_limit_read'] <= param <= p['channel3_voltage_limit_read']:
            self.voltage_limit_changed.emit(param.index, new_value)

        elif p['channel0_polarity_read'] <= param <= p['channel3_polarity_read']:
            self.polarity_changed.emit(param.index, new_value)

        elif p['channel0_current_read'] <= param <= p['channel3_current_read']:
            self.actual_current_changed.emit(param.index, new_value)

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

    def set_voltage_limit(self, channel, voltage, unit_label='raw', response_handler=None):
        return self.set_parameter_by_name('channel%d_voltage_limit_write' % channel, voltage, unit_label, response_handler)


    def get_actual_current(self, channel):
        pass

    def get_current_limit(self, channel):
        pass

    def set_current_limit(self, channel, current, unit_label='raw', response_handler=None):
        return self.set_parameter_by_name('channel%d_current_limit_write' % channel, current, unit_label, response_handler)


    def get_channel_state(self, channel):
        pass

    def set_channel_state(self, channel, on_off, response_handler=None):
        return self.set_parameter_by_name('channel%d_enable_write' % channel, bool(on_off), 'raw', response_handler)

    def get_polarity(self, channel):
        pass

    def set_polarity(self, channel, polarity, response_handler=None):
        return self.set_parameter_by_name('channel%d_polarity_write' % channel, polarity, 'raw', response_handler)

    def get_maximum_voltage(self):
        if self.profile.name == 'MHV-4-800V':
            return 800.0
        return 400.0

class ChannelWidget(QtGui.QWidget):
    target_voltage_changed  = pyqtSignal(float)
    channel_state_changed   = pyqtSignal(bool)
    current_limit_changed   = pyqtSignal(float)
    voltage_limit_changed   = pyqtSignal(float)
    polarity_changed        = pyqtSignal(int)

    def __init__(self, mhv4, channel, parent=None):
        super(ChannelWidget, self).__init__(parent)
        uic.loadUi(application_registry.instance.find_data_file('mesycontrol/ui/mhv4_channel.ui'), self)
        self.mhv4    = weakref.ref(mhv4)
        self.channel = channel
        self.voltage_limit_was_set = False
        self.current_limit_was_set = False

        self.spin_actual_voltage_limit.setMaximum(mhv4.get_maximum_voltage())
        self.spin_target_voltage_limit.setMaximum(mhv4.get_maximum_voltage())

    def set_voltage(self, voltage):
        self.lcd_voltage.display(voltage)

    def set_target_voltage(self, voltage):
        if self.spin_target_voltage.maximum() < voltage:
            self.set_voltage_limit(voltage)

        with util.block_signals(self.slider_target_voltage):
            self.slider_target_voltage.setValue(voltage)

        with util.block_signals(self.spin_target_voltage):
            self.spin_target_voltage.setValue(voltage)

    def set_voltage_limit(self, voltage):
        self.spin_actual_voltage_limit.setValue(voltage)
        self.spin_target_voltage.setMaximum(voltage)
        self.slider_target_voltage.setMaximum(voltage)
        self.slider_target_voltage.setTickInterval(100 if voltage >= 100.0 else 10)

        if not self.voltage_limit_was_set:
            self.spin_target_voltage_limit.setValue(voltage)
            self.voltage_limit_was_set = True

    def set_current(self, current):
        self.lcd_current.display(current)

    def set_current_limit(self, current):
        self.spin_actual_current_limit.setValue(current)

        if not self.current_limit_was_set:
            self.spin_target_current_limit.setValue(current)
            self.current_limit_was_set = True

    def set_channel_state(self, on_off):
        with util.block_signals(self.cb_channel_state):
            self.cb_channel_state.setChecked(on_off)

    def set_polarity(self, polarity):
        text = "positive" if polarity == Polarity.positive else "negative"
        self.le_actual_polarity.setText(text)

    @pyqtSlot(int)
    def on_slider_target_voltage_valueChanged(self, value):
        with util.block_signals(self.spin_target_voltage):
            self.spin_target_voltage.setValue(value)

    @pyqtSlot()
    def on_slider_target_voltage_sliderReleased(self):
        self.target_voltage_changed.emit(self.slider_target_voltage.value())

    @pyqtSlot(float)
    def on_spin_target_voltage_valueChanged(self, value):
        with util.block_signals(self.slider_target_voltage):
            self.slider_target_voltage.setValue(value)

    @pyqtSlot()
    def on_spin_target_voltage_editingFinished(self):
        self.target_voltage_changed.emit(self.spin_target_voltage.value())

    @pyqtSlot(int)
    def on_cb_channel_state_stateChanged(self, value):
        self.channel_state_changed.emit(self.cb_channel_state.isChecked())

    @pyqtSlot()
    def on_pb_applySettings_clicked(self):
        self.current_limit_changed.emit(self.spin_target_current_limit.value())
        self.voltage_limit_changed.emit(self.spin_target_voltage_limit.value())
        self.polarity_changed.emit(self.combo_target_polarity.currentIndex())

class MHV4Widget(QtGui.QWidget):
    def __init__(self, device, parent=None):
        super(MHV4Widget, self).__init__(parent)

        self.device = device
        self.device.add_default_parameter_subscription(self)

        self.device.actual_voltage_changed.connect(self.actual_voltage_changed)
        self.device.target_voltage_changed.connect(self.target_voltage_changed)
        self.device.voltage_limit_changed.connect(self.voltage_limit_changed)
        self.device.actual_current_changed.connect(self.actual_current_changed)
        self.device.current_limit_changed.connect(self.current_limit_changed)
        self.device.channel_state_changed.connect(self.channel_state_changed)
        self.device.polarity_changed.connect(self.polarity_changed)


        channel_layout = QtGui.QHBoxLayout()
        channel_layout.setContentsMargins(4, 4, 4, 4)

        self.channels = list()

        for i in range(4):
            groupbox        = QtGui.QGroupBox("Channel %d" % (i+1), self)
            channel_widget  = ChannelWidget(device, i, groupbox)
            groupbox_layout = QtGui.QHBoxLayout(groupbox)
            groupbox_layout.setContentsMargins(4, 4, 4, 4)
            groupbox_layout.addWidget(channel_widget)
            channel_layout.addWidget(groupbox)

            channel_widget.target_voltage_changed.connect(self.set_target_voltage)
            channel_widget.voltage_limit_changed.connect(self.set_voltage_limit)
            channel_widget.current_limit_changed.connect(self.set_current_limit)
            channel_widget.channel_state_changed.connect(self.set_channel_state)
            channel_widget.polarity_changed.connect(self.set_polarity)

            self.channels.append(weakref.ref(channel_widget))

        vbox = QtGui.QVBoxLayout(self)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.addItem(channel_layout)

    @pyqtSlot(float)
    def set_target_voltage(self, voltage):
        self.device.set_target_voltage(self.sender().channel, voltage, 'V')

    @pyqtSlot(float)
    def set_voltage_limit(self, voltage):
        self.device.set_voltage_limit(self.sender().channel, voltage, 'V')

    @pyqtSlot(float)
    def set_current_limit(self, current):
        self.device.set_current_limit(self.sender().channel, current, 'µA')

    @pyqtSlot(bool)
    def set_channel_state(self, on_off):
        self.device.set_channel_state(self.sender().channel, on_off)

    @pyqtSlot(int)
    def set_polarity(self, polarity):
        self.device.set_polarity(self.sender().channel, polarity)

    # FIXME: convert raw values to units using device profile information

    def actual_voltage_changed(self, channel, value):
        self.channels[channel]().set_voltage(value / 10.0)

    def target_voltage_changed(self, channel, value):
        self.channels[channel]().set_target_voltage(value / 10.0)

    def voltage_limit_changed(self, channel, value):
        self.channels[channel]().set_voltage_limit(value / 10.0)

    def actual_current_changed(self, channel, value):
        self.channels[channel]().set_current(value / 1000.0)

    def current_limit_changed(self, channel, value):
        self.channels[channel]().set_current_limit(value / 1000.0)

    def channel_state_changed(self, channel, value):
        self.channels[channel]().set_channel_state(value)

    def polarity_changed(self, channel, value):
        self.channels[channel]().set_polarity(value)
