#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import uic
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import pyqtSlot
from PyQt4.QtCore import Qt
from functools import partial
import math
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
    """Model for the 800V MHV-4 high voltage supply."""
    num_channels  = 4
    idcs          = (27,)

    ramp_speeds = {
            0:   '5 V/s',
            1:  '25 V/s',
            2: '100 V/s',
            3: '500 V/s'
            }

    tcomp_sources = {
            0: '0',
            1: '1',
            2: '2',
            3: '3',
            4: 'off'
            }

    temp_no_sensor = 999

    actual_voltage_changed  = pyqtSignal([int, int], [object])   #: [channel, raw value], [BoundParameter]
    target_voltage_changed  = pyqtSignal([int, int], [object])   #: [channel, raw value], [BoundParameter]
    voltage_limit_changed   = pyqtSignal([int, int], [object])   #: [channel, raw value], [BoundParameter]
    actual_current_changed  = pyqtSignal([int, int], [object])   #: [channel, raw value], [BoundParameter]
    current_limit_changed   = pyqtSignal([int, int], [object])   #: [channel, raw value], [BoundParameter]
    channel_state_changed   = pyqtSignal(int, bool)              #: channel, value
    polarity_changed        = pyqtSignal(int, int)               #: channel, Polarity.(negative|positive)
    temperature_changed     = pyqtSignal([int, int], [object])   #: [channel, raw_value], [BoundParameter]
    tcomp_slope_changed     = pyqtSignal([int, int], [object])    
    tcomp_offset_changed    = pyqtSignal([int, int], [object])
    tcomp_source_changed    = pyqtSignal([int, int], [object])
    ramp_speed_changed      = pyqtSignal(int)

    def __init__(self, device_model=None, device_config=None, device_profile=None, parent=None):
        super(MHV4, self).__init__(device_model=device_model, device_config=device_config,
                device_profile=device_profile, parent=parent)

        self.log = util.make_logging_source_adapter(__name__, self)

        self.parameter_changed[object, int, int].connect(self._on_parameter_changed)

    def propagate_state(self):
        """Propagate the current state using the signals defined in this class."""
        if not self.has_model():
            return

        for param_profile in self.profile.parameters:
            if self.has_parameter(param_profile.address):
                self._on_parameter_changed(param_profile, 0, self[param_profile.address])

    def _on_parameter_changed(self, param, old_value, new_value):
        p = self.profile

        if p['channel0_voltage_write'] <= param <= p['channel3_voltage_write']:
            self.target_voltage_changed.emit(param.index, new_value)
            self.target_voltage_changed[object].emit(self.make_bound_parameter(param))

        elif p['channel0_voltage_read'] <= param <= p['channel3_voltage_read']:
            self.actual_voltage_changed.emit(param.index, new_value)
            self.actual_voltage_changed[object].emit(self.make_bound_parameter(param))

        elif p['channel0_enable_read'] <= param <= p['channel3_enable_read']:
            self.channel_state_changed.emit(param.index, new_value)

        elif p['channel0_current_limit_read'] <= param <= p['channel3_current_limit_read']:
            self.current_limit_changed.emit(param.index, new_value)
            self.current_limit_changed[object].emit(self.make_bound_parameter(param))

        elif p['channel0_voltage_limit_read'] <= param <= p['channel3_voltage_limit_read']:
            self.voltage_limit_changed.emit(param.index, new_value)
            self.voltage_limit_changed[object].emit(self.make_bound_parameter(param))

        elif p['channel0_polarity_read'] <= param <= p['channel3_polarity_read']:
            self.polarity_changed.emit(param.index, new_value)

        elif p['channel0_current_read'] <= param <= p['channel3_current_read']:
            self.actual_current_changed.emit(param.index, new_value)
            self.actual_current_changed[object].emit(self.make_bound_parameter(param))

        elif p['channel0_temp_read'] <= param <= p['channel3_temp_read']:
            self.temperature_changed.emit(param.index, new_value)
            self.temperature_changed[object].emit(self.make_bound_parameter(param))

        elif p['channel0_tcomp_slope_read'] <= param <= p['channel3_tcomp_slope_read']:
            self.tcomp_slope_changed.emit(param.index, new_value)
            self.tcomp_slope_changed[object].emit(self.make_bound_parameter(param))

        elif p['channel0_tcomp_offset_read'] <= param <= p['channel3_tcomp_offset_read']:
            self.tcomp_offset_changed.emit(param.index, new_value)
            self.tcomp_offset_changed[object].emit(self.make_bound_parameter(param))

        elif p['channel0_tcomp_source_read'] <= param <= p['channel3_tcomp_source_read']:
            self.tcomp_source_changed.emit(param.index, new_value)
            self.tcomp_source_changed[object].emit(self.make_bound_parameter(param))

        elif p['ramp_speed_read'] == param:
            self.ramp_speed_changed.emit(new_value)

    # voltage
    def get_actual_voltage(self, channel, unit_label='raw'):
        return self.get_parameter_by_name('channel%d_voltage_read' % channel, unit_label)

    def get_target_voltage(self, channel, unit_label='raw'):
        return self.get_parameter_by_name('channel%d_voltage_write' % channel, unit_label)

    def set_target_voltage(self, channel, voltage, unit_label='raw', response_handler=None):
        return self.set_parameter_by_name('channel%d_voltage_write' % channel, voltage, unit_label, response_handler)

    def get_voltage_limit(self, channel, unit_label='raw'):
        return self.get_parameter_by_name('channel%d_voltage_limit_read' % channel, unit_label)

    def set_voltage_limit(self, channel, voltage, unit_label='raw', response_handler=None):
        return self.set_parameter_by_name('channel%d_voltage_limit_write' % channel, voltage, unit_label, response_handler)

    # current
    def get_actual_current(self, channel, unit_label='raw'):
        return self.get_parameter_by_name('channel%d_current_read' % channel, unit_label)

    def get_current_limit(self, channel, unit_label='raw'):
        return self.get_parameter_by_name('channel%d_current_limit_read' % channel, unit_label)

    def set_current_limit(self, channel, current, unit_label='raw', response_handler=None):
        return self.set_parameter_by_name('channel%d_current_limit_write' % channel, current, unit_label, response_handler)


    # channel state
    def get_channel_state(self, channel):
        return bool(self.get_parameter_by_name('channel%d_enable_read' % channel))

    def set_channel_state(self, channel, on_off, response_handler=None):
        return self.set_parameter_by_name('channel%d_enable_write' % channel, bool(on_off), 'raw', response_handler)

    def enable_all_channels(self):
        for i in range(MHV4.num_channels):
            self.set_channel_state(i, True)

    # polarity
    def get_polarity(self, channel):
        return self.get_parameter_by_name('channel%d_polarity_read' % channel)

    def set_polarity(self, channel, polarity, response_handler=None):
        return self.set_parameter_by_name('channel%d_polarity_write' % channel, polarity, 'raw', response_handler)

    # temperature compensation
    def get_tcomp_slope(self, channel, unit_label='raw'):
        return self.get_parameter_by_name('channel%d_tcomp_slope_read' % channel, unit_label)

    def set_tcomp_slope(self, channel, value, unit_label='raw', response_handler=None):
        self.set_parameter_by_name('channel%d_tcomp_slope_write' % channel, value, unit_label, response_handler)

    def get_tcomp_offset(self, channel, unit_label='raw'):
        return self.get_parameter_by_name('channel%d_tcomp_offset_read' % channel, unit_label)

    def set_tcomp_offset(self, channel, value, unit_label='raw', response_handler=None):
        self.set_parameter_by_name('channel%d_tcomp_offset_write' % channel, value, unit_label, response_handler)

    def get_tcomp_source(self, channel):
        return self.get_parameter_by_name('channel%d_tcomp_source_read' % channel)

    def set_tcomp_source(self, channel, value, unit_label='raw', response_handler=None):
        self.set_parameter_by_name('channel%d_tcomp_source_write' % channel, value, unit_label, response_handler)

    # ramp speed
    def get_ramp_speed(self):
        return self.get_parameter_by_name('ramp_speed_read')

    def set_ramp_speed(self, value, response_handler=None):
        return self.set_parameter_by_name('ramp_speed_write', value, 'raw', response_handler)

    def get_maximum_voltage(self):
        return 800.0

class ChannelWidget(QtGui.QWidget):
    target_voltage_changed          = pyqtSignal(float)
    channel_state_changed           = pyqtSignal(bool)

    def __init__(self, mhv4, channel, parent=None):
        super(ChannelWidget, self).__init__(parent)
        uic.loadUi(application_registry.instance.find_data_file('mesycontrol/ui/mhv4_channel_without_settings.ui'), self)
        self.mhv4    = weakref.ref(mhv4)
        self.channel = channel

        self.pb_channelstate.installEventFilter(self)
        reg = application_registry.instance
        sz  = self.label_polarity.minimumSize()
        self.pixmap_positive = QtGui.QPixmap(reg.find_data_file('mesycontrol/ui/list-add.png')).scaled(
                        sz, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.pixmap_negative = QtGui.QPixmap(reg.find_data_file('mesycontrol/ui/list-remove.png')).scaled(
                        sz, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self._last_temperature      = None
        self._last_tcomp_source     = None
        self._last_current          = None
        self._last_current_limit    = None

    def set_voltage(self, voltage):
        self.lcd_voltage.display(float(voltage))

    def set_target_voltage(self, voltage):
        if self.spin_target_voltage.maximum() < voltage:
            self.set_voltage_limit(voltage)

        with util.block_signals(self.slider_target_voltage):
            self.slider_target_voltage.setValue(voltage)

        with util.block_signals(self.spin_target_voltage):
            self.spin_target_voltage.setValue(voltage)

    def set_voltage_limit(self, voltage):
        self.spin_target_voltage.setMaximum(voltage)
        self.slider_target_voltage.setMaximum(voltage)
        self.slider_target_voltage.setTickInterval(100 if voltage > 100.0 else 10)
        self.label_upper_voltage_limit.setText("%.1f V" % voltage)

    def set_current(self, current):
        self._last_current = current
        self._update_current_display()

    def set_current_limit(self, current):
        self._last_current_limit = current
        self._update_current_display()

    def _update_current_display(self):
        if self._last_current is None:
            return

        self.lcd_current.display(float(self._last_current))

        if (self._last_current_limit is not None
                and math.fabs(self._last_current) >= self._last_current_limit):
            self.lcd_current.setStyleSheet('QLCDNumber { color: red; }')
        else:
            self.lcd_current.setStyleSheet('QLCDNumber { color: black; }')

        if self._last_current_limit is not None:
            text = QtCore.QString.fromUtf8("Limit: %.3f µA" % self._last_current_limit)
            self.lcd_current.setToolTip(text)
            self.lcd_current.setStatusTip(text)

    def set_channel_state(self, on_off):
        with util.block_signals(self.pb_channelstate):
            self.pb_channelstate.setChecked(on_off)
            self.pb_channelstate.setText("On" if on_off else "Off")

        self.label_polarity.setEnabled(on_off)

    def set_polarity(self, polarity):
        if polarity == Polarity.positive:
            pixmap = self.pixmap_positive
            tooltip = 'Polarity: positive'
        else:
            pixmap = self.pixmap_negative
            tooltip = 'Polarity: negative'

        self.label_polarity.setPixmap(pixmap)
        self.label_polarity.setToolTip(tooltip)
        self.label_polarity.setStatusTip(tooltip)

    def set_temperature(self, deg_celsius):
        self._last_temperature = deg_celsius
        self._update_temperature_display()

    def set_tcomp_source(self, source):
        self._last_tcomp_source = source
        self._update_temperature_display()

    def _update_temperature_display(self):
        if (self._last_tcomp_source is None
                or MHV4.tcomp_sources[self._last_tcomp_source] == 'off'):
            self.label_temperature.clear()
            return

        if self._last_temperature is None:
            text = "Temp: -"
        else:
            text = QtCore.QString.fromUtf8("Temp: %.1f °C" % self._last_temperature)

        if self._last_tcomp_source is not None:
            text += ", Src: %s" % MHV4.tcomp_sources[self._last_tcomp_source]

        self.label_temperature.setText(text)

    @pyqtSlot(int)
    def on_slider_target_voltage_valueChanged(self, value):
        with util.block_signals(self.spin_target_voltage):
            self.spin_target_voltage.setValue(value)

        slider = self.slider_target_voltage
        slider.setToolTip("%d V" % value)

        if slider.isVisible():
            cursor_pos = QtGui.QCursor.pos()
            global_pos = slider.mapToGlobal(slider.rect().topRight())
            global_pos.setY(cursor_pos.y())

            tooltip_event = QtGui.QHelpEvent(QtCore.QEvent.ToolTip,
                    QtCore.QPoint(0, 0), global_pos)

            QtGui.QApplication.sendEvent(slider, tooltip_event)

    @pyqtSlot()
    def on_slider_target_voltage_sliderReleased(self):
        self.target_voltage_changed.emit(self.slider_target_voltage.value())
        self.slider_target_voltage.setToolTip("%d V" % self.slider_target_voltage.value())

    @pyqtSlot(float)
    def on_spin_target_voltage_valueChanged(self, value):
        with util.block_signals(self.slider_target_voltage):
            self.slider_target_voltage.setValue(value)

    @pyqtSlot()
    def on_spin_target_voltage_editingFinished(self):
        self.target_voltage_changed.emit(self.spin_target_voltage.value())

    @pyqtSlot(bool)
    def on_pb_channelstate_toggled(self, value):
        c = self.pb_channelstate.isChecked()
        self.channel_state_changed.emit(c)

    def eventFilter(self, watched_object, event):
        if watched_object == self.pb_channelstate:
            t = event.type()
            c = self.pb_channelstate.isChecked()

            if t == QtCore.QEvent.Enter:
                if c:
                    self.pb_channelstate.setText("Turn\n off ")
                else:
                    self.pb_channelstate.setText("Turn\n on")
            elif t == QtCore.QEvent.Leave:
                if c:
                    self.pb_channelstate.setText("On")
                else:
                    self.pb_channelstate.setText("Off")

        return False

class ChannelSettingsWidget(QtGui.QWidget):
    def __init__(self, mhv4, channel, labels_on=True, parent=None):
        super(ChannelSettingsWidget, self).__init__(parent)

        uic.loadUi(application_registry.instance.find_data_file('mesycontrol/ui/mhv4_channel_settings.ui'), self)
        self.mhv4    = weakref.ref(mhv4)
        self.channel = channel

        if not labels_on:
            for label in self.findChildren(QtGui.QLabel, QtCore.QRegExp("label_\\d+")):
                label.hide()

        self.spin_target_voltage_limit.setMaximum(mhv4.get_maximum_voltage())

    def set_voltage_limit(self, value):
        self.spin_actual_voltage_limit.setValue(value)
        self.spin_target_voltage_limit.setValue(value)

    def set_current_limit(self, value):
        self.spin_actual_current_limit.setValue(value)
        self.spin_target_current_limit.setValue(value)

    def set_polarity(self, value):
        text = "positive" if value == Polarity.positive else "negative"
        self.le_actual_polarity.setText(text)
        self.combo_target_polarity.setCurrentIndex(value)

    def set_tcomp_slope(self, value):
        self.spin_actual_tcomp_slope.setValue(value)
        self.spin_target_tcomp_slope.setValue(value)

    def set_tcomp_offset(self, value):
        self.spin_actual_tcomp_offset.setValue(value)
        self.spin_target_tcomp_offset.setValue(value)

    def set_tcomp_source(self, value):
        self.le_actual_tcomp_source.setText(MHV4.tcomp_sources[value])
        self.combo_target_tcomp_source.setCurrentIndex(value)

class MHV4Widget(QtGui.QWidget):
    def __init__(self, device, parent=None):
        super(MHV4Widget, self).__init__(parent)

        self.device = device
        self.device.add_default_parameter_subscription(self)

        self.channels = list()
        self.channel_settings = list()
        self.global_settings = None

        # Channel controls
        channel_layout = QtGui.QHBoxLayout()
        channel_layout.setContentsMargins(4, 4, 4, 4)

        for i in range(MHV4.num_channels):
            groupbox        = QtGui.QGroupBox("Channel %d" % (i+1), self)
            channel_widget  = ChannelWidget(device, i)
            groupbox_layout = QtGui.QHBoxLayout(groupbox)
            groupbox_layout.setContentsMargins(4, 4, 4, 4)
            groupbox_layout.addWidget(channel_widget)
            channel_layout.addWidget(groupbox)

            channel_widget.target_voltage_changed.connect(self.set_target_voltage)
            channel_widget.channel_state_changed.connect(self.set_channel_state)

            self.channels.append(weakref.ref(channel_widget))

        # Channel settings
        channel_settings_layout = QtGui.QHBoxLayout()
        channel_settings_layout.setContentsMargins(4, 4, 4, 4)

        for i in range(MHV4.num_channels):
            groupbox        = QtGui.QGroupBox("Channel %d" % (i+1), self)
            settings_widget = ChannelSettingsWidget(device, i, i == 0)
            groupbox_layout = QtGui.QHBoxLayout(groupbox)
            groupbox_layout.setContentsMargins(4, 4, 4, 4)
            groupbox_layout.addWidget(settings_widget)
            channel_settings_layout.addWidget(groupbox)
            
            self.channel_settings.append(weakref.ref(settings_widget))

        # Global settings
        global_settings_widget = uic.loadUi(application_registry.instance.find_data_file(
            'mesycontrol/ui/mhv4_global_settings.ui'))
        self.global_settings = weakref.ref(global_settings_widget)

        # Settings apply button
        pb_apply_settings = QtGui.QPushButton("Apply", clicked=self.apply_settings)
        apply_button_layout = QtGui.QHBoxLayout()
        apply_button_layout.addStretch(1)
        apply_button_layout.addWidget(pb_apply_settings)
        apply_button_layout.addStretch(1)

        settings_layout = QtGui.QVBoxLayout()
        settings_layout.setContentsMargins(4, 4, 4, 4)
        settings_layout.addItem(channel_settings_layout)
        settings_layout.addWidget(global_settings_widget)
        settings_layout.addItem(apply_button_layout)
        container_widget = QtGui.QWidget()
        container_widget.setLayout(settings_layout)

        channels_widget = QtGui.QWidget()
        channels_widget.setLayout(channel_layout)

        toolbox = QtGui.QToolBox()
        toolbox.addItem(channels_widget, QtGui.QIcon(application_registry.instance.find_data_file(
            'mesycontrol/ui/applications-utilities.png')), 'Channel Control')
        toolbox.addItem(container_widget, QtGui.QIcon(application_registry.instance.find_data_file(
            'mesycontrol/ui/preferences-system.png')), 'Settings')

        layout = QtGui.QVBoxLayout() 
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toolbox)
        self.setLayout(layout)

        self.device.actual_voltage_changed.connect(self.actual_voltage_changed)
        self.device.target_voltage_changed.connect(self.target_voltage_changed)
        self.device.voltage_limit_changed.connect(self.voltage_limit_changed)
        self.device.actual_current_changed.connect(self.actual_current_changed)
        self.device.current_limit_changed.connect(self.current_limit_changed)
        self.device.channel_state_changed.connect(self.channel_state_changed)
        self.device.polarity_changed.connect(self.polarity_changed)
        self.device.temperature_changed[object].connect(self.temperature_changed)
        self.device.tcomp_slope_changed[object].connect(self.tcomp_slope_changed)
        self.device.tcomp_offset_changed[object].connect(self.tcomp_offset_changed)
        self.device.tcomp_source_changed[object].connect(self.tcomp_source_changed)
        self.device.ramp_speed_changed.connect(self.ramp_speed_changed)

        # Initialize the GUI with the current state of the device. This is
        # needed to make newly created widgets work even if all static
        # parameters are known (static parameters won't get refreshed and thus
        # no change signals will be emitted).
        self.device.propagate_state()

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

    def actual_voltage_changed(self, channel, value):
        unit_value = self.device.profile['channel0_voltage_read'].get_unit('V').unit_value(value)
        self.channels[channel]().set_voltage(unit_value)

    def target_voltage_changed(self, channel, value):
        unit_value = self.device.profile['channel0_voltage_write'].get_unit('V').unit_value(value)
        self.channels[channel]().set_target_voltage(unit_value)

    def voltage_limit_changed(self, channel, value):
        unit_value = self.device.profile['channel0_voltage_limit_write'].get_unit('V').unit_value(value)
        self.channels[channel]().set_voltage_limit(unit_value)
        self.channel_settings[channel]().set_voltage_limit(unit_value)

    def actual_current_changed(self, channel, value):
        unit_value = self.device.profile['channel0_current_read'].get_unit('µA').unit_value(value)
        self.channels[channel]().set_current(unit_value)

    def current_limit_changed(self, channel, value):
        unit_value = self.device.profile['channel0_current_limit_read'].get_unit('µA').unit_value(value)
        self.channels[channel]().set_current_limit(unit_value)
        self.channel_settings[channel]().set_current_limit(unit_value)

    def channel_state_changed(self, channel, value):
        self.channels[channel]().set_channel_state(value)

    def polarity_changed(self, channel, value):
        self.channels[channel]().set_polarity(value)
        self.channel_settings[channel]().set_polarity(value)

    def temperature_changed(self, bp):
        if bp.value == MHV4.temp_no_sensor:
            value = None
        else:
            value = bp.get_value('°C')

        self.channels[bp.index]().set_temperature(value)

    def tcomp_slope_changed(self, bp):
        self.channel_settings[bp.index]().set_tcomp_slope(bp.get_value('V/°C'))

    def tcomp_offset_changed(self, bp):
        self.channel_settings[bp.index]().set_tcomp_offset(bp.get_value('°C'))

    def tcomp_source_changed(self, bp):
        self.channels[bp.index]().set_tcomp_source(bp.value)
        self.channel_settings[bp.index]().set_tcomp_source(bp.value)

    def ramp_speed_changed(self, value):
        self.global_settings().combo_target_ramp_speed.setCurrentIndex(value)
        self.global_settings().le_actual_ramp_speed.setText(
                self.global_settings().combo_target_ramp_speed.currentText())

    def apply_settings(self, checked):
        def set_if_differs(cur, new, setter):
            if cur != new:
                setter(new)
                return True
            return False

        d  = self.device

        set_if_differs(
                cur=d.get_ramp_speed(),
                new=self.global_settings().combo_target_ramp_speed.currentIndex(),
                setter=d.set_ramp_speed)

        for i in range(MHV4.num_channels):
            cs = self.channel_settings[i]()

            changed = set_if_differs(
                    cur=d.get_polarity(i),
                    new=cs.combo_target_polarity.currentIndex(),
                    setter=partial(d.set_polarity, i))

            if changed:
                self.channels[i]().set_target_voltage(.0)

            set_if_differs(
                    cur=d.get_current_limit(i, 'µA'),
                    new=cs.spin_target_current_limit.value(),
                    setter=partial(d.set_current_limit, i, unit_label='µA'))

            set_if_differs(
                    cur=d.get_voltage_limit(i, 'V'),
                    new=cs.spin_target_voltage_limit.value(),
                    setter=partial(d.set_voltage_limit, i, unit_label='V'))

            set_if_differs(
                    cur=d.get_tcomp_slope(i, 'V/°C'),
                    new=cs.spin_target_tcomp_slope.value(),
                    setter=partial(d.set_tcomp_slope, i, unit_label='V/°C'))

            set_if_differs(
                    cur=d.get_tcomp_offset(i, '°C'),
                    new=cs.spin_target_tcomp_offset.value(),
                    setter=partial(d.set_tcomp_offset, i, unit_label='°C'))

            set_if_differs(
                    cur=d.get_tcomp_source(i),
                    new=cs.combo_target_tcomp_source.currentIndex(),
                    setter=partial(d.set_tcomp_source, i))
