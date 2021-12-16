#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2021 mesytec GmbH & Co. KG <info@mesytec.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

__author__ = 'Florian Lüke'
__email__  = 'f.lueke@mesytec.com'

from .. qt import Slot
from .. qt import Qt
from .. qt import QtCore
from .. qt import QtGui
from .. qt import QtWidgets

import itertools
import weakref

from .. import parameter_binding as pb
from .. import util
from .. specialized_device import DeviceBase
from .. specialized_device import DeviceWidgetBase

import mesycontrol.devices.mhv4_profile as mhv4_profile

NUM_CHANNELS = 4

RAMP_SPEEDS = {
        0:   '5 V/s',
        1:  '25 V/s',
        2: '100 V/s',
        3: '500 V/s'
        }

TCOMP_SOURCES = {
        0: '0',
        1: '1',
        2: '2',
        3: '3',
        4: 'off'
        }

TCOMP_SOURCE_OFF = 4

NUM_TEMP_SENSORS = 4
TEMP_NO_SENSOR = 999
MAX_VOLTAGE_V  = 800.0

Polarity = mhv4_profile.Polarity

# ==========  Device ==========
class MHV4(DeviceBase):
    def __init__(self, app_device, display_mode, write_mode, parent=None):
        super(MHV4, self).__init__(app_device, display_mode, write_mode, parent)

        params = ('channel%d_polarity_write' % i for i in range(NUM_CHANNELS))
        self._polarity_write_addresses = [self.profile[pn].address for pn in params]

    def _on_hw_parameter_changed(self, address, value):
        super(MHV4, self)._on_hw_parameter_changed(address, value)

        if self.write_mode & util.HARDWARE and address in self._polarity_write_addresses:
            index = self.profile[address].index
            self.set_parameter('channel%d_voltage_write' % index, 0)

# ==========  GUI ==========
class WheelEventFilter(QtCore.QObject):
    """Event filter to filter out QEvent::Wheel events."""
    def __init__(self, parent=None):
        super(WheelEventFilter, self).__init__(parent)

    def eventFilter(self, obj, event):
        return event.type() == QtCore.QEvent.Wheel

class PolarityLabelBinding(pb.DefaultParameterBinding):
    def __init__(self, pixmaps, **kwargs):
        super(PolarityLabelBinding, self).__init__(**kwargs)

        self._pixmaps = pixmaps

    def _update(self, rf):
        try:
            self.target.setPixmap(self._pixmaps[int(rf.result())])
        except Exception:
            pass

class ChannelEnablePolarityBinding(pb.DefaultParameterBinding):
    """Used for the polarity label. Disables/enables the label depending on the
    channels enable state."""
    def __init__(self, **kwargs):
        super(ChannelEnablePolarityBinding, self).__init__(**kwargs)

    def _update(self, rf):
        self.target.setEnabled(int(rf.result()))

class ChannelEnableButtonBinding(pb.DefaultParameterBinding):
    def __init__(self, **kwargs):
        super(ChannelEnableButtonBinding, self).__init__(**kwargs)
        self.target.clicked.connect(self._button_clicked)

    def _update(self, rf):
        is_enabled = int(rf.result())
        self.target.setChecked(is_enabled)
        self.target.setText("On" if is_enabled else "Off")

    def _button_clicked(self, checked):
        self._write_value(int(checked))

class ChannelWidget(QtWidgets.QWidget):
    def __init__(self, device, channel, display_mode, write_mode, parent=None):
        super(ChannelWidget, self).__init__(parent)
        self.ui = util.loadUi(":/ui/mhv4_channel.ui", self)
        self.device  = device
        self.channel = channel
        self.bindings = list()

        self.ui.pb_channelstate.installEventFilter(self)
        sz  = self.ui.label_polarity.minimumSize()

        self.polarity_pixmaps = {
                Polarity.positive: QtGui.QPixmap(":/polarity-positive.png").scaled(
                    sz, Qt.KeepAspectRatio, Qt.SmoothTransformation),

                Polarity.negative: QtGui.QPixmap(":/polarity-negative.png").scaled(
                    sz, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                }

        self._last_temperature      = None
        self._last_tcomp_source     = None

        self.ui.slider_target_voltage.installEventFilter(WheelEventFilter(self))

        # Voltage write
        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['channel%d_voltage_write' % channel],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.ui.spin_target_voltage,
            unit_name='volt'))

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['channel%d_voltage_write' % channel],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.ui.slider_target_voltage,
            unit_name='volt', update_on='slider_released'))

        # Polarity
        self.bindings.append(PolarityLabelBinding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_polarity_read' % channel],
                device.profile['channel%d_polarity_write' % channel]),
            target=self.ui.label_polarity, display_mode=display_mode, write_mode=write_mode,
            pixmaps=self.polarity_pixmaps))

        # Channel enable
        self.bindings.append(ChannelEnablePolarityBinding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_enable_read' % channel],
                device.profile['channel%d_enable_write' % channel]),
            target=self.ui.label_polarity, display_mode=display_mode, write_mode=write_mode))

        self.bindings.append(ChannelEnableButtonBinding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_enable_read' % channel],
                device.profile['channel%d_enable_write' % channel]),
            target=self.ui.pb_channelstate, display_mode=display_mode, write_mode=write_mode))

        # Voltage
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['channel%d_voltage_read' % channel],
            target=self.ui.lcd_voltage, display_mode=display_mode, write_mode=write_mode,
            unit_name='volt', precision=2))

        # Voltage limit
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_voltage_limit_read' % channel],
                device.profile['channel%d_voltage_limit_write' % channel]),
            target=self.ui.label_upper_voltage_limit, display_mode=display_mode, write_mode=write_mode,
            unit_name='volt').add_update_callback(self._voltage_limit_updated))

        # Current
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['channel%d_current_read' % channel],
            target=self.ui.lcd_current, display_mode=display_mode, write_mode=write_mode,
            unit_name='microamps', precision=3
            ).add_update_callback(self._current_updated))

        # Current limit
        self.bindings.append(pb.TargetlessParameterBinding(
            device=device, profile=device.profile['channel%d_current_limit_read' % channel],
            display_mode=display_mode, write_mode=write_mode
            ).add_update_callback(self._current_limit_updated))

        # Sensors
        for i in range(NUM_TEMP_SENSORS):
            self.bindings.append(pb.TargetlessParameterBinding(
                device=device, profile=device.profile['sensor%d_temp_read' % i],
                display_mode=display_mode, write_mode=write_mode
                ).add_update_callback(self._sensor_temperature_changed))

        # TComp source
        self.bindings.append(pb.TargetlessParameterBinding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_tcomp_source_read' % channel],
                device.profile['channel%d_tcomp_source_write' % channel]),
            display_mode=display_mode, write_mode=write_mode
            ).add_update_callback(self._tcomp_source_changed))

    def _voltage_limit_updated(self, rf):
        unit    = self.device.profile[rf.result().address].get_unit('volt')
        voltage = unit.unit_value(int(rf.result()))

        self.ui.spin_target_voltage.setMaximum(voltage)
        self.ui.slider_target_voltage.setMaximum(voltage)
        self.ui.slider_target_voltage.setTickInterval(100 if voltage > 200.0 else 10)

    def _current_updated(self, f_current):
        def done(f_current_limit):
            self._update_current_lcd_color(f_current, f_current_limit)

        self.device.get_parameter('channel%d_current_limit_read' % self.channel
                ).add_done_callback(done)

    def _current_limit_updated(self, f_current_limit):
        def done(f_current):
            self._update_current_lcd_color(f_current, f_current_limit)

        self.device.get_parameter('channel%d_current_read' % self.channel
                ).add_done_callback(done)

    def _update_current_lcd_color(self, f_current, f_current_limit):
        # Set LCD color to red if current limit is exceeded
        try:
            limit       = int(f_current_limit)
            current     = abs(int(f_current))

            color       = 'red' if current >= limit else 'black'
            css         = 'QLCDNumber { color: %s; }' % color

            self.lcd_current.setStyleSheet(css)
        except (KeyError, TypeError):
            pass

    def _sensor_temperature_changed(self, rf_sensor):
        try:
            sensor_profile  = self.device.profile[rf_sensor.result().address]
            sensor_num      = sensor_profile.index
        except pb.ParameterUnavailable:
            return

        def tcomp_source_done(rf_source):
            source = int(rf_source)

            if source == sensor_num:
                self._update_temperature_display(rf_source, rf_sensor)

        if self.device.read_mode != util.HARDWARE:
            return

        self.device.get_parameter('channel%d_tcomp_source_read' % self.channel
                ).add_done_callback(tcomp_source_done)

    def _tcomp_source_changed(self, rf_source):
        source = int(rf_source)

        if source == TCOMP_SOURCE_OFF:
            self._update_temperature_display(rf_source, None)
        else:
            def sensor_read_done(rf_sensor):
                self._update_temperature_display(rf_source, rf_sensor)

            if self.device.read_mode != util.HARDWARE:
                return

            self.device.get_parameter('sensor%d_temp_read' % source
                    ).add_done_callback(sensor_read_done)

    def _update_temperature_display(self, f_source, f_sensor):

        if f_sensor is None:
            self.ui.label_temperature.clear()
        else:
            source_str  = TCOMP_SOURCES[int(f_source)]
            try:
                temp_raw    = int(f_sensor)
            except (KeyError, IndexError):
                temp_raw    = TEMP_NO_SENSOR

            if temp_raw == TEMP_NO_SENSOR:
                text = "Temp: -, Src: %s" % source_str
            else:
                unit = self.device.profile['sensor0_temp_read'].get_unit(
                        'degree_celcius')

                temperature = unit.unit_value(temp_raw)

                text = "Temp: %.1f °C, Src: %s" % (temperature, source_str)

            self.ui.label_temperature.setText(text)

    @Slot(int)
    def on_slider_target_voltage_valueChanged(self, value):
        slider = self.slider_target_voltage
        slider.setToolTip("%d V" % value)

        if slider.isVisible():
            cursor_pos = QtWidgets.QCursor.pos()
            global_pos = slider.mapToGlobal(slider.rect().topRight())
            global_pos.setY(cursor_pos.y())

            tooltip_event = QtWidgets.QHelpEvent(QtCore.QEvent.ToolTip,
                    QtCore.QPoint(0, 0), global_pos)

            QtWidgets.QApplication.sendEvent(slider, tooltip_event)

    def eventFilter(self, watched_object, event):
        if watched_object == self.ui.pb_channelstate:
            t = event.type()
            c = self.ui.pb_channelstate.isChecked()

            if t == QtCore.QEvent.Enter:
                if c:
                    self.ui.pb_channelstate.setText("Turn\n off ")
                else:
                    self.ui.pb_channelstate.setText("Turn\n on")
            elif t == QtCore.QEvent.Leave:
                if c:
                    self.ui.pb_channelstate.setText("On")
                else:
                    self.ui.pb_channelstate.setText("Off")

        return False

class ChannelSettingsWidget(QtWidgets.QWidget):
    def __init__(self, device, channel, display_mode, write_mode, labels_on=True, parent=None):
        super(ChannelSettingsWidget, self).__init__(parent)

        self.ui = util.loadUi(":/ui/mhv4_channel_settings.ui", self)
        self.device  = device
        self.channel = channel
        self.bindings = list()

        self.display_mode = display_mode
        self.write_mode   = write_mode

        if not labels_on:
            for label in self.findChildren(QtWidgets.QLabel, QtCore.QRegExp("label_\\d+")):
                label.hide()

        # Voltage limit
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_voltage_limit_read' % channel],
                device.profile['channel%d_voltage_limit_write' % channel]),
            display_mode=display_mode, write_mode=write_mode,
            target=self.ui.spin_actual_voltage_limit, unit_name='volt'))

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_voltage_limit_read' % channel],
                device.profile['channel%d_voltage_limit_write' % channel]),
            display_mode=display_mode, write_mode=write_mode,
            target=self.ui.spin_target_voltage_limit, unit_name='volt'))

        # Current limit
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_current_limit_read' % channel],
                device.profile['channel%d_current_limit_write' % channel]),
            display_mode=display_mode, write_mode=write_mode,
            target=self.ui.spin_actual_current_limit, unit_name='microamps'))

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_current_limit_read' % channel],
                device.profile['channel%d_current_limit_write' % channel]),
            display_mode=display_mode, write_mode=write_mode,
            target=self.ui.spin_target_current_limit, unit_name='microamps'))

        # Polarity
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_polarity_read' % channel],
                device.profile['channel%d_polarity_write' % channel]),
            display_mode=display_mode, write_mode=write_mode,
            target=self.ui.combo_target_polarity
            ).add_update_callback(self._polarity_updated))

        # TComp Slope
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_tcomp_slope_read' % channel],
                device.profile['channel%d_tcomp_slope_write' % channel]),
            display_mode=display_mode, write_mode=write_mode,
            target=self.ui.spin_actual_tcomp_slope, unit_name='volt_per_deg'))

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_tcomp_slope_read' % channel],
                device.profile['channel%d_tcomp_slope_write' % channel]),
            display_mode=display_mode, write_mode=write_mode,
            target=self.ui.spin_target_tcomp_slope, unit_name='volt_per_deg'))

        # TComp Offset
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_tcomp_offset_read' % channel],
                device.profile['channel%d_tcomp_offset_write' % channel]),
            display_mode=display_mode, write_mode=write_mode,
            target=self.ui.spin_actual_tcomp_offset, unit_name='degree_celcius'))

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_tcomp_offset_read' % channel],
                device.profile['channel%d_tcomp_offset_write' % channel]),
            display_mode=display_mode, write_mode=write_mode,
            target=self.ui.spin_target_tcomp_offset, unit_name='degree_celcius'))

        # TComp Source
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_tcomp_source_read' % channel],
                device.profile['channel%d_tcomp_source_write' % channel]),
            display_mode=display_mode, write_mode=write_mode,
            target=self.ui.combo_target_tcomp_source
            ).add_update_callback(self._tcomp_source_updated))

    def _polarity_updated(self, rf):
        dev = self.device.cfg if self.display_mode == util.CONFIG else self.device.hw
        rw  = 'read' if dev is self.device.hw else 'write'

        n = 'channel%d_polarity_%s' % (self.channel, rw)
        p = self.device.profile[n]
        r = rf.result()

        if r.address == p.address:
            text = self.ui.combo_target_polarity.itemData(r.value, Qt.DisplayRole)
            self.ui.le_actual_polarity.setText(text)

    def _tcomp_source_updated(self, rf):
        dev = self.device.cfg if self.display_mode == util.CONFIG else self.device.hw
        rw  = 'read' if dev is self.device.hw else 'write'

        n = 'channel%d_tcomp_source_%s' % (self.channel, rw)
        p = self.device.profile[n]
        r = rf.result()

        if r.address == p.address:
            text = self.ui.combo_target_tcomp_source.itemData(r.value, Qt.DisplayRole)
            self.ui.le_actual_tcomp_source.setText(text)

class GlobalSettingsWidget(QtWidgets.QWidget):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(GlobalSettingsWidget, self).__init__(parent)

        self.ui = util.loadUi(":/ui/mhv4_global_settings.ui", self)
        self.device = device
        self.bindings = list()

        self.display_mode = display_mode
        self.write_mode   = write_mode

        # Ramp speed
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['ramp_speed_read'],
                device.profile['ramp_speed_write']),
            display_mode=display_mode, write_mode=write_mode,
            target=self.ui.combo_target_ramp_speed
            ).add_update_callback(self._ramp_speed_updated))

    def _ramp_speed_updated(self, rf):
        dev = self.device.cfg if self.display_mode == util.CONFIG else self.device.hw
        rw  = 'read' if dev is self.device.hw else 'write'

        n = 'ramp_speed_%s' % rw
        p = self.device.profile[n]
        r = rf.result()

        if r.address == p.address:
            text = self.ui.combo_target_ramp_speed.itemData(r.value, Qt.DisplayRole)
            self.ui.le_actual_ramp_speed.setText(text)

class MHV4Widget(DeviceWidgetBase):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(MHV4Widget, self).__init__(device, display_mode, write_mode, parent)

        self.channels = list()
        self.settings_widgets = list()

        # Channel controls
        channel_layout = QtWidgets.QHBoxLayout()
        channel_layout.setContentsMargins(4, 4, 4, 4)

        for i in range(NUM_CHANNELS):
            groupbox        = QtWidgets.QGroupBox("Channel %d" % i, self)
            channel_widget  = ChannelWidget(device, i, display_mode, write_mode)
            groupbox_layout = QtWidgets.QHBoxLayout(groupbox)
            groupbox_layout.setContentsMargins(4, 4, 4, 4)
            groupbox_layout.addWidget(channel_widget)
            channel_layout.addWidget(groupbox)

            self.channels.append(weakref.ref(channel_widget))

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(channel_layout)

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.tab_widget.addTab(widget, device.profile.name)
        self.settings_bindings = self._add_settings_tab()

    def get_parameter_bindings(self):
        bindings = list()

        for cw in self.channels:
            bindings.append(cw().bindings)

        bindings.extend(self.settings_bindings)

        return itertools.chain(*bindings)

    def clear_parameter_bindings(self):
        for cw in self.channels:
            cw().bindings = list()

        for sw in self.settings_widgets:
            sw().bindings = list()

    def _add_settings_tab(self):
        bindings = list()
        tabs = QtWidgets.QTabWidget()

        for i in range(NUM_CHANNELS):
            csw = ChannelSettingsWidget(self.device, i, self.display_mode, self.write_mode)
            tabs.addTab(csw, "Channel %d" % i)
            bindings.append(csw.bindings)
            self.settings_widgets.append(weakref.ref(csw))

        gsw = GlobalSettingsWidget(self.device, self.display_mode, self.write_mode)
        tabs.addTab(gsw, "Global")
        bindings.append(gsw.bindings)
        self.settings_widgets.append(weakref.ref(gsw))

        self.tab_widget.addTab(tabs, "Settings")

        for b in itertools.chain(*bindings):
            b.populate()

        return bindings

idc             = 27
device_class    = MHV4
device_ui_class = MHV4Widget
profile_dict    = mhv4_profile.profile_dict
