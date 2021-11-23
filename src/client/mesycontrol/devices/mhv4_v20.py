#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2016 mesytec GmbH & Co. KG <info@mesytec.com>
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

import itertools
import weakref

from .. import parameter_binding as pb
from .. import util
from .. specialized_device import DeviceBase
from .. specialized_device import DeviceWidgetBase

import mhv4_v20_profile

NUM_CHANNELS = 4
MAX_VOLTAGE_V  = 400.0

Polarity = mhv4_v20_profile.Polarity

# ==========  Device ==========
class MHV4_V20(DeviceBase):
    def __init__(self, app_device, display_mode, write_mode, parent=None):
        super(MHV4_V20, self).__init__(app_device, display_mode, write_mode, parent)

    def _on_hw_parameter_changed(self, address, value):
        super(MHV4_V20, self)._on_hw_parameter_changed(address, value)

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
            self.target.setPixmap(self._pixmaps[int(rf)])
        except Exception:
            pass

class ChannelEnablePolarityBinding(pb.DefaultParameterBinding):
    """Used for the polarity label. Disables/enables the label depending on the
    channels enable state."""
    def __init__(self, **kwargs):
        super(ChannelEnablePolarityBinding, self).__init__(**kwargs)

    def _update(self, rf):
        self.target.setEnabled(int(rf))

class ChannelEnableButtonBinding(pb.DefaultParameterBinding):
    def __init__(self, **kwargs):
        super(ChannelEnableButtonBinding, self).__init__(**kwargs)
        self.target.clicked.connect(self._button_clicked)

    def _update(self, rf):
        is_enabled = int(rf)
        self.target.setChecked(is_enabled)
        self.target.setText("On" if is_enabled else "Off")

    def _button_clicked(self, checked):
        self._write_value(int(checked))

class ChannelWidget(QtGui.QWidget):
    def __init__(self, device, channel, display_mode, write_mode, parent=None):
        super(ChannelWidget, self).__init__(parent)
        util.loadUi(":/ui/mhv4_v20_channel.ui", self)
        self.device  = device
        self.channel = channel
        self.bindings = list()

        self.pb_channelstate.installEventFilter(self)
        sz  = self.label_polarity.minimumSize()

        self.polarity_pixmaps = {
                Polarity.positive: QtGui.QPixmap(":/polarity-positive.png").scaled(
                    sz, Qt.KeepAspectRatio, Qt.SmoothTransformation),

                Polarity.negative: QtGui.QPixmap(":/polarity-negative.png").scaled(
                    sz, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                }

        self._last_temperature      = None
        self._last_tcomp_source     = None

        self.slider_target_voltage.installEventFilter(WheelEventFilter(self))

        # Voltage write
        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['channel%d_voltage_write' % channel],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_target_voltage,
            unit_name='volt'))

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['channel%d_voltage_write' % channel],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.slider_target_voltage,
            unit_name='volt', update_on='slider_released'))

        # Polarity
        self.bindings.append(PolarityLabelBinding(
            device=device, profile=device.profile['channel%d_polarity_read' % channel],
            target=self.label_polarity, display_mode=display_mode, write_mode=write_mode,
            pixmaps=self.polarity_pixmaps))

        # Channel enable
        self.bindings.append(ChannelEnablePolarityBinding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_enable_read' % channel],
                device.profile['channel%d_enable_write' % channel]),
            target=self.label_polarity, display_mode=display_mode, write_mode=write_mode))

        self.bindings.append(ChannelEnableButtonBinding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['channel%d_enable_read' % channel],
                device.profile['channel%d_enable_write' % channel]),
            target=self.pb_channelstate, display_mode=display_mode, write_mode=write_mode))

        # Voltage
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['channel%d_voltage_read' % channel],
            target=self.lcd_voltage, display_mode=display_mode, write_mode=write_mode,
            unit_name='volt', precision=2))

        # Voltage limit label
        self.bindings.append(pb.TargetlessParameterBinding(
            device=device, profile=device.profile['voltage_range_read'],
            display_mode=display_mode, write_mode=write_mode
            ).add_update_callback(self._voltage_range_updated))

        # Current
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['channel%d_current_read' % channel],
            target=self.lcd_current, display_mode=display_mode, write_mode=write_mode,
            unit_name='microamps', precision=3
            ).add_update_callback(self._current_updated))

        # Current limit
        self.bindings.append(pb.TargetlessParameterBinding(
            device=device, profile=device.profile['channel%d_current_limit_read' % channel],
            display_mode=display_mode, write_mode=write_mode
            ).add_update_callback(self._current_limit_updated))

    def _voltage_range_updated(self, rf):

        voltage_range = int(rf)
        voltage = 100 if voltage_range == mhv4_v20_profile.VoltageRange.range_100v else 400

        self.spin_target_voltage.setMaximum(voltage)
        self.slider_target_voltage.setMaximum(voltage)
        self.slider_target_voltage.setTickInterval(100 if voltage > 200.0 else 10)
        self.label_upper_voltage_limit.setText(str(voltage) + " V")


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

    @Slot(int)
    def on_slider_target_voltage_valueChanged(self, value):
        slider = self.slider_target_voltage
        slider.setToolTip("%d V" % value)

        if slider.isVisible():
            cursor_pos = QtGui.QCursor.pos()
            global_pos = slider.mapToGlobal(slider.rect().topRight())
            global_pos.setY(cursor_pos.y())

            tooltip_event = QtGui.QHelpEvent(QtCore.QEvent.ToolTip,
                    QtCore.QPoint(0, 0), global_pos)

            QtGui.QApplication.sendEvent(slider, tooltip_event)

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

class SettingsWidget(QtGui.QWidget):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(SettingsWidget, self).__init__(parent)

        util.loadUi(":/ui/mhv4_v20_settings.ui", self)

        self.device = device
        self.bindings = list()
        self.display_mode = display_mode
        self.write_mode   = write_mode

        curLimit_actual_spins = [
                self.spin_actual_current_limit0,
                self.spin_actual_current_limit1,
                self.spin_actual_current_limit2,
                self.spin_actual_current_limit3
                ]

        curLimit_target_spins = [
                self.spin_target_current_limit0,
                self.spin_target_current_limit1,
                self.spin_target_current_limit2,
                self.spin_target_current_limit3
                ]

        for channel in range(NUM_CHANNELS):
            self.bindings.append(pb.factory.make_binding(
                device=device, profile=pb.ReadWriteProfile(
                    device.profile['channel%d_current_limit_read' % channel],
                    device.profile['channel%d_current_limit_write' % channel]),
                display_mode=display_mode, write_mode=write_mode,
                target=curLimit_actual_spins[channel], unit_name='microamps'))

            self.bindings.append(pb.factory.make_binding(
                device=device, profile=pb.ReadWriteProfile(
                    device.profile['channel%d_current_limit_read' % channel],
                    device.profile['channel%d_current_limit_write' % channel]),
                display_mode=display_mode, write_mode=write_mode,
                target=curLimit_target_spins[channel], unit_name='microamps'))

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=pb.ReadWriteProfile(
                device.profile['voltage_range_read'],
                device.profile['voltage_range_write']),
            display_mode=display_mode, write_mode=write_mode,
            target=self.combo_target_voltage_range
            ).add_update_callback(self._voltage_range_updated))

    def _voltage_range_updated(self, rf):
        dev = self.device.cfg if self.display_mode == util.CONFIG else self.device.hw
        rw  = 'read' if dev is self.device.hw else 'write'

        n = 'voltage_range_%s' % rw
        p = self.device.profile[n]
        r = rf.result()

        if r.address == p.address:
            text = self.combo_target_voltage_range.itemData(r.value, Qt.DisplayRole).toString()
            self.le_actual_voltage_range.setText(text)

class MHV4_V20_Widget(DeviceWidgetBase):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(MHV4_V20_Widget, self).__init__(device, display_mode, write_mode, parent)

        self.channels = list()
        self.settings_widget = None

        # Channel controls
        channel_layout = QtGui.QHBoxLayout()
        channel_layout.setContentsMargins(4, 4, 4, 4)

        for i in range(NUM_CHANNELS):
            groupbox        = QtGui.QGroupBox("Channel %d" % i, self)
            channel_widget  = ChannelWidget(device, i, display_mode, write_mode)
            groupbox_layout = QtGui.QHBoxLayout(groupbox)
            groupbox_layout.setContentsMargins(4, 4, 4, 4)
            groupbox_layout.addWidget(channel_widget)
            channel_layout.addWidget(groupbox)

            self.channels.append(weakref.ref(channel_widget))

        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(channel_layout)

        widget = QtGui.QWidget()
        widget.setLayout(layout)
        self.tab_widget.addTab(widget, device.profile.name)


        sw = SettingsWidget(self.device, self.display_mode, self.write_mode)
        self.tab_widget.addTab(sw, "Settings")
        self.settings_widget = weakref.ref(sw)

        for b in self.get_parameter_bindings():
            b.populate()

    def get_parameter_bindings(self):
        bindings = list()

        for cw in self.channels:
            bindings.append(cw().bindings)

        bindings.append(self.settings_widget().bindings)

        return itertools.chain(*bindings)

    def clear_parameter_bindings(self):
        for cw in self.channels:
            cw().bindings = list()

        self.settings_widget().bindings = list()

idc             = 17
device_class    = MHV4_V20
device_ui_class = MHV4_V20_Widget
profile_dict    = mhv4_v20_profile.profile_dict
