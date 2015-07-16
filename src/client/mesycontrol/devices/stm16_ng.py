#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from .. qt import pyqtSignal
from .. qt import pyqtSlot
from .. qt import Qt
from .. qt import QtCore
from .. qt import QtGui

from functools import partial

from .. future import set_result_on
from .. import future
from .. import parameter_binding as pb
from .. import util
from .. specialized_device import DeviceBase
from .. util import hline
from .. util import make_spinbox
from .. util import make_title_label

import device_profile_stm16

NUM_CHANNELS        = 16        # number of channels
NUM_GROUPS          =  8        # number of channel groups
GAIN_FACTOR         = 1.22      # gain step factor
GAIN_ADJUST_LIMITS  = (1, 100)  # limits of the hardware gain jumpers

cg_helper = util.ChannelGroupHelper(NUM_CHANNELS, NUM_GROUPS)

class STM16(DeviceBase):
    gain_adjust_changed = pyqtSignal(int)

    def __init__(self, app_device, read_mode, write_mode, parent=None):
        super(STM16, self).__init__(app_device, read_mode, write_mode, parent)

        # Init gain adjust from the device profile
        self._gain_adjust = self.profile.get_extension('gain_adjust')

        self.config_set.connect(self._on_config_set)

    def get_gain_adjust(self):
        if self.has_cfg:
            return self.cfg.get_extension('gain_adjust')

        return self._gain_adjust

    def set_gain_adjust(self, gain_adjust):
        changed = self.get_gain_adjust() != gain_adjust

        if self.has_cfg:
            self.cfg.set_extension('gain_adjust', int(gain_adjust))
        else:
            self._gain_adjust = int(gain_adjust)

        if changed:
            self.gain_adjust_changed.emit(self.get_gain_adjust())

    def get_total_gain(self, group):
        ret = future.Future()

        @set_result_on(ret)
        def done(f):
            return GAIN_FACTOR ** int(f) * self.get_gain_adjust()

        self.get_parameter('gain_group%d' % group).add_done_callback(done)

        return ret

    def _on_config_set(self):
        # Call set_gain_adjust with the internally stored value. This will set
        # gain adjust on the config if there is one.
        self.set_gain_adjust(self._gain_adjust)

dynamic_label_style = "QLabel { background-color: lightgrey; }"

class GainPage(QtGui.QGroupBox):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(GainPage, self).__init__("Gain", parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self.device = device

        device.gain_adjust_changed.connect(self._on_device_gain_adjust_changed)

        self.gain_inputs    = list()
        self.gain_labels    = list()
        self.hw_gain_input  = None
        self.bindings       = list()

        layout = QtGui.QGridLayout(self)

        layout.addWidget(make_title_label("Group"),   1, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("RC Gain"), 1, 1, 1, 1, Qt.AlignCenter)
        layout.addWidget(make_title_label("Total"),   1, 2, 1, 1, Qt.AlignCenter)

        offset = layout.rowCount()

        for i in range(NUM_GROUPS):
            group_range = cg_helper.group_channel_range(i)
            descr_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1]))
            gain_spin   = util.DelayedSpinBox()

            binding = pb.factory.make_binding(
                device=device,
                profile=device.profile['gain_group%d' % i],
                display_mode=display_mode,
                write_mode=write_mode,
                target=gain_spin)

            def cb(f, group):
                self._update_gain_label(group)

            binding.add_update_callback(partial(cb, group=i))

            self.bindings.append(binding)

            gain_label  = QtGui.QLabel("N/A")
            gain_label.setStyleSheet(dynamic_label_style)

            self.gain_inputs.append(gain_spin)
            self.gain_labels.append(gain_label)

            layout.addWidget(descr_label, i+offset, 0, 1, 1, Qt.AlignRight)
            layout.addWidget(gain_spin,   i+offset, 1)
            layout.addWidget(gain_label,  i+offset, 2, 1, 1, Qt.AlignCenter)

        layout.addWidget(hline(), layout.rowCount(), 0, 1, 3) # hline separator

        layout.addWidget(make_title_label("Gain Jumper"), layout.rowCount(), 0, 1, 3, Qt.AlignCenter)

        offset = layout.rowCount()

        self.hw_gain_input = make_spinbox(limits=GAIN_ADJUST_LIMITS)
        self.hw_gain_input.setValue(device.get_gain_adjust())
        self.hw_gain_input.valueChanged[int].connect(self._on_hw_gain_input_value_changed)

        layout.addWidget(self.hw_gain_input, offset, 1)

    @pyqtSlot(int)
    def _on_hw_gain_input_value_changed(self, value):
        self.device.set_gain_adjust(value)

    def _on_device_gain_adjust_changed(self, value):
        with util.block_signals(self.hw_gain_input):
            self.hw_gain_input.setValue(value)

        for i in range(NUM_GROUPS):
            self._update_gain_label(i)

    def _update_gain_label(self, group):
        def done(f):
            try:
                self.gain_labels[group].setText("%.1f" % f.result())
            except Exception as e:
                self.log.warning("_update_gain_label: %s: %s", type(e), e)
                self.gain_labels[group].setText("N/A")

        self.device.get_total_gain(group).add_done_callback(done)

class TimingPage(QtGui.QGroupBox):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(TimingPage, self).__init__("Timing", parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self.device = device

        self.threshold_inputs = list()
        self.threshold_labels = list()
        self.bindings = list()

        layout = QtGui.QGridLayout(self)

        layout.addWidget(make_title_label("Channel"),   1, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Threshold"), 1, 1)

        for chan in range(NUM_CHANNELS):
            offset  = 2
            descr_label     = QtGui.QLabel("%d" % chan)
            spin_threshold  = util.DelayedSpinBox()
            label_threshold = QtGui.QLabel()
            label_threshold.setStyleSheet(dynamic_label_style)

            layout.addWidget(descr_label,       chan+offset, 0, 1, 1, Qt.AlignRight)
            layout.addWidget(spin_threshold,    chan+offset, 1)
            layout.addWidget(label_threshold,   chan+offset, 2)

            self.threshold_inputs.append(spin_threshold)
            self.threshold_labels.append(label_threshold)

            self.bindings.append(pb.factory.make_binding(
                device=device,
                profile=self.device.profile['threshold_channel%d' % chan],
                display_mode=display_mode,
                write_mode=write_mode,
                target=spin_threshold))

            self.bindings.append(pb.factory.make_binding(
                device=device,
                profile=self.device.profile['threshold_channel%d' % chan],
                display_mode=display_mode,
                unit_name='percent',
                target=label_threshold))

class STM16Widget(QtGui.QWidget):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(STM16Widget, self).__init__(parent)
        self.device  = device

        self.gain_page   = GainPage(device, display_mode, write_mode, self)
        self.timing_page = TimingPage(device, display_mode, write_mode, self)

        self.pages = [self.gain_page, self.timing_page]

        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(*(4 for i in range(4)))
        layout.setSpacing(4)

        for page in self.pages:
            vbox = QtGui.QVBoxLayout()
            vbox.addWidget(page)
            vbox.addStretch(1)
            layout.addItem(vbox)
            page.installEventFilter(self)

    def set_display_mode(self, display_mode):
        for page in self.pages:
            for binding in page.bindings:
                binding.set_display_mode(display_mode)

    def set_write_mode(self, write_mode):
        for page in self.pages:
            for binding in page.bindings:
                binding.set_write_mode(write_mode)

    def eventFilter(self, watched_object, event):
        # Populate pages on show events

        if (event.type() == QtCore.QEvent.Show
                and not event.spontaneous()
                and hasattr(watched_object, 'bindings')):

            for b in watched_object.bindings:
                b.populate()

        return False

idc             = 19
device_class    = STM16
device_ui_class = STM16Widget
profile_dict    = device_profile_stm16.profile_dict
