#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import uic
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import pyqtSlot
from PyQt4.QtCore import Qt
from functools import partial
import math
import weakref

import app_model
import util

# TODO: improve modified state for ChannelSettingsWidget and
# GlobalSettingsWidget: compare spinbox value to old value and set modified
# state accordingly
# FIXME: toggling polarity does not set the devices target voltage to zero.
# this means turning a channel on after a polarity change will ramp to the
# previous voltage with inverted polarity. Despite this the voltage slider and
# spinbox display 0V which is wrong!

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
    temperature_changed     = pyqtSignal([int, int], [object])   #: [sensor_idx, raw_value], [BoundParameter]
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

        elif p['sensor0_temp_read'] <= param <= p['sensor3_temp_read']:
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

    def get_temperature(self, sensor, unit_label='°C'):
        return self.get_parameter_by_name('sensor%d_temp_read' % sensor, unit_label)

    # ramp speed
    def get_ramp_speed(self):
        return self.get_parameter_by_name('ramp_speed_read')

    def set_ramp_speed(self, value, response_handler=None):
        return self.set_parameter_by_name('ramp_speed_write', value, 'raw', response_handler)

    def get_maximum_voltage(self):
        return 800.0

class WheelEventFilter(QtCore.QObject):
    """Event filter to filter out QEvent::Wheel events."""
    def __init__(self, parent=None):
        super(WheelEventFilter, self).__init__(parent)

    def eventFilter(self, obj, event):
        return event.type() == QtCore.QEvent.Wheel

class ChannelWidget(QtGui.QWidget):
    target_voltage_changed          = pyqtSignal(float)
    channel_state_changed           = pyqtSignal(bool)

    def __init__(self, mhv4, channel, context, parent=None):
        super(ChannelWidget, self).__init__(parent)
        uic.loadUi(context.find_data_file('mesycontrol/ui/mhv4_channel_without_settings.ui'), self)
        self.mhv4    = weakref.ref(mhv4)
        self.channel = channel

        self.pb_channelstate.installEventFilter(self)
        sz  = self.label_polarity.minimumSize()
        self.pixmap_positive = QtGui.QPixmap(context.find_data_file('mesycontrol/ui/list-add.png')).scaled(
                        sz, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.pixmap_negative = QtGui.QPixmap(context.find_data_file('mesycontrol/ui/list-remove.png')).scaled(
                        sz, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self._last_temperature      = None
        self._last_tcomp_source     = None
        self._last_current          = None
        self._last_current_limit    = None

        self.slider_target_voltage.installEventFilter(WheelEventFilter(self))

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
    apply_settings      = pyqtSignal()
    modified_changed    = pyqtSignal(bool)

    def __init__(self, mhv4, channel, context, labels_on=True, parent=None):
        super(ChannelSettingsWidget, self).__init__(parent)

        self.mhv4    = weakref.ref(mhv4)
        self.channel = channel
        uic.loadUi(context.find_data_file('mesycontrol/ui/mhv4_channel_settings.ui'), self)

        if not labels_on:
            for label in self.findChildren(QtGui.QLabel, QtCore.QRegExp("label_\\d+")):
                label.hide()

        self.spin_target_voltage_limit.setMaximum(mhv4.get_maximum_voltage())
        self.pb_apply.clicked.connect(self.apply_settings)
        self.pb_discard.clicked.connect(self.discard)

        self.spin_target_voltage_limit.valueChanged.connect(partial(self.set_modified, True))
        self.spin_target_current_limit.valueChanged.connect(partial(self.set_modified, True))
        self.combo_target_polarity.currentIndexChanged.connect(partial(self.set_modified, True))
        self.spin_target_tcomp_slope.valueChanged.connect(partial(self.set_modified, True))
        self.spin_target_tcomp_offset.valueChanged.connect(partial(self.set_modified, True))
        self.combo_target_tcomp_source.currentIndexChanged.connect(partial(self.set_modified, True))
        self._modified = False

    def set_modified(self, is_modified):
        if self.modified != is_modified:
            self._modified = is_modified
            self.modified_changed.emit(is_modified)

    def is_modified(self):
        return self._modified

    def set_voltage_limit(self, value):
        self.spin_actual_voltage_limit.setValue(value)
        with util.block_signals(self.spin_target_voltage_limit):
            self.spin_target_voltage_limit.setValue(value)

    def set_current_limit(self, value):
        self.spin_actual_current_limit.setValue(value)
        with util.block_signals(self.spin_target_current_limit):
            self.spin_target_current_limit.setValue(value)

    def set_polarity(self, value):
        text = "positive" if value == Polarity.positive else "negative"
        self.le_actual_polarity.setText(text)
        with util.block_signals(self.combo_target_polarity):
            self.combo_target_polarity.setCurrentIndex(value)

    def set_tcomp_slope(self, value):
        self.spin_actual_tcomp_slope.setValue(value)
        with util.block_signals(self.spin_target_tcomp_slope):
            self.spin_target_tcomp_slope.setValue(value)

    def set_tcomp_offset(self, value):
        self.spin_actual_tcomp_offset.setValue(value)
        with util.block_signals(self.spin_target_tcomp_offset):
            self.spin_target_tcomp_offset.setValue(value)

    def set_tcomp_source(self, value):
        self.le_actual_tcomp_source.setText(MHV4.tcomp_sources[value])
        with util.block_signals(self.combo_target_tcomp_source):
            self.combo_target_tcomp_source.setCurrentIndex(value)

    def get_voltage_limit(self):
        return self.spin_target_voltage_limit.value()

    def get_current_limit(self):
        return self.spin_target_current_limit.value()

    def get_polarity(self):
        return self.combo_target_polarity.currentIndex()

    def get_tcomp_slope(self):
        return self.spin_target_tcomp_slope.value()

    def get_tcomp_offset(self):
        return self.spin_target_tcomp_offset.value()

    def get_tcomp_source(self):
        return self.combo_target_tcomp_source.currentIndex()

    def discard(self):
        self.spin_target_voltage_limit.setValue(self.spin_actual_voltage_limit.value())
        self.spin_target_current_limit.setValue(self.spin_actual_current_limit.value())
        self.combo_target_polarity.setCurrentIndex(self.mhv4().get_polarity(self.channel))
        self.spin_target_tcomp_slope.setValue(self.spin_actual_tcomp_slope.value())
        self.spin_target_tcomp_offset.setValue(self.spin_actual_tcomp_offset.value())
        self.combo_target_tcomp_source.setCurrentIndex(self.mhv4().get_tcomp_source(self.channel))
        self.modified = False

    modified = pyqtProperty(bool, is_modified, set_modified, notify=modified_changed)

class GlobalSettingsWidget(QtGui.QWidget):
    apply_settings      = pyqtSignal()
    modified_changed    = pyqtSignal(bool)

    def __init__(self, mhv4, context, parent=None):
        super(GlobalSettingsWidget, self).__init__(parent)

        uic.loadUi(context.find_data_file('mesycontrol/ui/mhv4_global_settings.ui'), self)
        self.mhv4 = weakref.ref(mhv4)
        self.pb_apply.clicked.connect(self.apply_settings)
        self.pb_discard.clicked.connect(self.discard)

        self.combo_target_ramp_speed.currentIndexChanged.connect(partial(self.set_modified, True))

        self._modified = False

    def set_modified(self, is_modified):
        if self.modified != is_modified:
            self._modified = is_modified
            self.modified_changed.emit(is_modified)

    def is_modified(self):
        return self._modified

    def set_ramp_speed(self, value):
        with util.block_signals(self.combo_target_ramp_speed):
            self.combo_target_ramp_speed.setCurrentIndex(value)
        self.le_actual_ramp_speed.setText(self.combo_target_ramp_speed.currentText())

    def get_ramp_speed(self):
        return self.combo_target_ramp_speed.currentIndex()

    def discard(self):
        self.combo_target_ramp_speed.setCurrentIndex(self.mhv4().get_ramp_speed())
        self.modified = False

    modified = pyqtProperty(bool, is_modified, set_modified, notify=modified_changed)

def set_if_differs(cur, new, setter):
    if cur != new:
        setter(new)
        return True
    return False

class MHV4Widget(QtGui.QWidget):
    def __init__(self, device, context, parent=None):
        super(MHV4Widget, self).__init__(parent)
        self.context = context
        self.device  = device
        self.device.add_default_parameter_subscription(self)

        self.channels = list()
        self.channel_settings = list()
        self.global_settings = None

        # Channel controls
        channel_layout = QtGui.QHBoxLayout()
        channel_layout.setContentsMargins(4, 4, 4, 4)

        for i in range(MHV4.num_channels):
            groupbox        = QtGui.QGroupBox("Channel %d" % (i+1), self)
            channel_widget  = ChannelWidget(device, i, self.context)
            groupbox_layout = QtGui.QHBoxLayout(groupbox)
            groupbox_layout.setContentsMargins(4, 4, 4, 4)
            groupbox_layout.addWidget(channel_widget)
            channel_layout.addWidget(groupbox)

            channel_widget.target_voltage_changed.connect(self.set_target_voltage)
            channel_widget.channel_state_changed.connect(self.set_channel_state)

            self.channels.append(weakref.ref(channel_widget))

        # Channel settings
        channel_settings_tabs = QtGui.QTabWidget()
        self.channel_settings_tabs = weakref.ref(channel_settings_tabs)

        for i in range(MHV4.num_channels):
            settings_widget = ChannelSettingsWidget(device, i, self.context)
            settings_widget.apply_settings.connect(self.apply_channel_settings)
            settings_widget.modified_changed.connect(self._on_channel_settings_modified)
            channel_settings_tabs.addTab(settings_widget, "Channel %d" % (i+1))
            self.channel_settings.append(weakref.ref(settings_widget))

        # Global settings
        global_settings_widget = GlobalSettingsWidget(device, self.context)
        global_settings_widget.apply_settings.connect(self.apply_global_settings)
        global_settings_widget.modified_changed.connect(self._on_global_settings_modified)
        self.global_settings = weakref.ref(global_settings_widget)
        channel_settings_tabs.addTab(global_settings_widget, "Global")

        channels_widget = QtGui.QWidget()
        channels_widget.setLayout(channel_layout)

        toolbox = QtGui.QToolBox()
        toolbox.addItem(channels_widget, QtGui.QIcon(self.context.find_data_file(
            'mesycontrol/ui/applications-utilities.png')), 'Channel Control')
        toolbox.addItem(channel_settings_tabs, QtGui.QIcon(self.context.find_data_file(
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

        sensor = bp.index

        # Update temperature for channels using this sensor
        for i in range(MHV4.num_channels):
            try:
                src = self.device.get_tcomp_source(i)
                if src == sensor:
                    self.channels[i]().set_temperature(value)
            except KeyError:
                pass

    def tcomp_slope_changed(self, bp):
        self.channel_settings[bp.index]().set_tcomp_slope(bp.get_value('V/°C'))

    def tcomp_offset_changed(self, bp):
        self.channel_settings[bp.index]().set_tcomp_offset(bp.get_value('°C'))

    def tcomp_source_changed(self, bp):
        self.channels[bp.index]().set_tcomp_source(bp.value)
        self.channel_settings[bp.index]().set_tcomp_source(bp.value)
        if MHV4.tcomp_sources[bp.value] == 'off':
            return

        try:
            temp = self.device.get_temperature(bp.value)
            self.channels[bp.index]().set_temperature(temp)
        except KeyError:
            pass

    def ramp_speed_changed(self, value):
        self.global_settings().set_ramp_speed(value)

    def _on_channel_settings_modified(self, is_modified):
        csw = self.sender()
        c   = csw.channel

        text = "Channel %d" % (c+1)
        if is_modified:
            text += "*"

        idx = self.channel_settings_tabs().indexOf(csw)
        self.channel_settings_tabs().setTabText(idx, text)

    def _on_global_settings_modified(self, is_modified):
        gsw = self.sender()
        text = "Global Settings"
        if is_modified:
            text += "*"

        idx = self.channel_settings_tabs().indexOf(gsw)
        self.channel_settings_tabs().setTabText(idx, text)

    def apply_channel_settings(self):
        csw = self.sender()
        d   = self.device
        c   = csw.channel

        changed = set_if_differs(
                cur=d.get_polarity(c),
                new=csw.get_polarity(),
                setter=partial(d.set_polarity, c))

        if changed:
            self.channels[c]().set_target_voltage(0)

        set_if_differs(
                cur=d.get_current_limit(c, 'µA'),
                new=csw.get_current_limit(),
                setter=partial(d.set_current_limit, c, unit_label='µA'))

        set_if_differs(
                cur=d.get_voltage_limit(c, 'V'),
                new=csw.get_voltage_limit(),
                setter=partial(d.set_voltage_limit, c, unit_label='V'))

        set_if_differs(
                cur=d.get_tcomp_slope(c, 'V/°C'),
                new=csw.get_tcomp_slope(),
                setter=partial(d.set_tcomp_slope, c, unit_label='V/°C'))

        set_if_differs(
                cur=d.get_tcomp_offset(c, '°C'),
                new=csw.get_tcomp_offset(),
                setter=partial(d.set_tcomp_offset, c, unit_label='°C'))

        set_if_differs(
                cur=d.get_tcomp_source(c),
                new=csw.get_tcomp_source(),
                setter=partial(d.set_tcomp_source, c))

        csw.modified = False

    def apply_global_settings(self):
        gsw = self.sender()
        d   = self.device

        set_if_differs(
                cur=d.get_ramp_speed(),
                new=gsw.get_ramp_speed(),
                setter=d.set_ramp_speed)

        gsw.modified = False
