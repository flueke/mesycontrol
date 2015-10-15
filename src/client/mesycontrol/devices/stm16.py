#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from .. qt import pyqtSignal
from .. qt import pyqtSlot
from .. qt import Qt
from .. qt import QtGui

import itertools

from .. future import set_result_on
from .. import future
from .. import parameter_binding as pb
from .. import util
from .. specialized_device import DeviceBase
from .. specialized_device import DeviceWidgetBase
from .. util import hline
from .. util import make_spinbox
from .. util import make_title_label

import stm16_profile

NUM_CHANNELS        = 16        # number of channels
NUM_GROUPS          =  8        # number of channel groups
GAIN_FACTOR         = 1.22      # gain step factor
GAIN_ADJUST_LIMITS  = (1, 100)  # limits of the hardware gain jumpers

cg_helper = util.ChannelGroupHelper(NUM_CHANNELS, NUM_GROUPS)

class STM16(DeviceBase):
    gain_adjust_changed = pyqtSignal(int)

    def __init__(self, app_device, read_mode, write_mode, parent=None):
        super(STM16, self).__init__(app_device, read_mode, write_mode, parent)
        self.extension_changed.connect(self._on_extension_changed)

    def get_gain_adjust(self):
        return self.get_extension('gain_adjust')

    def set_gain_adjust(self, gain_adjust):
        if self.get_gain_adjust() != gain_adjust:
            self.set_extension('gain_adjust', gain_adjust)
            self.gain_adjust_changed.emit(self.get_gain_adjust())

    def get_total_gain(self, group):
        ret = future.Future()

        @set_result_on(ret)
        def done(f):
            return GAIN_FACTOR ** int(f) * self.get_gain_adjust()

        self.get_parameter('gain_group%d' % group).add_done_callback(done)

        return ret

    def _on_extension_changed(self, name, value):
        if name == 'gain_adjust':
            self.gain_adjust_changed.emit(self.get_gain_adjust())

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

            binding.add_update_callback(self._update_gain_label_cb, group=i)

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
        self.log.debug("_on_hw_gain_input_value_changed: %s", value)
        self.device.set_gain_adjust(value)

    def _on_device_gain_adjust_changed(self, value):
        self.log.debug("_on_device_gain_adjust_changed: %s", value)
        with util.block_signals(self.hw_gain_input):
            self.hw_gain_input.setValue(value)

        for i in range(NUM_GROUPS):
            self._update_gain_label(i)

    # This version works as an update callback by accepting an additional
    # argument: the result_future passed to the callback.
    def _update_gain_label_cb(self, f, group):
        self.log.debug("_update_gain_label_cb: %s, %s", f, group)
        self._update_gain_label(group)

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

class STM16Widget(DeviceWidgetBase):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(STM16Widget, self).__init__(device, display_mode, write_mode, parent)
        self.device  = device

        self.gain_page   = GainPage(device, display_mode, write_mode)
        self.timing_page = TimingPage(device, display_mode, write_mode)

        self.pages = [self.gain_page, self.timing_page]

        layout = QtGui.QHBoxLayout()
        layout.setContentsMargins(*(4 for i in range(4)))
        layout.setSpacing(4)

        for page in self.pages:
            vbox = QtGui.QVBoxLayout()
            vbox.addWidget(page)
            vbox.addStretch(1)
            layout.addItem(vbox)
            page.installEventFilter(self)

        widget = QtGui.QWidget()
        widget.setLayout(layout)
        self.tab_widget.addTab(widget, device.profile.name)

    def get_parameter_bindings(self):
        return itertools.chain(*(p.bindings for p in self.pages))

idc             = 19
device_class    = STM16
device_ui_class = STM16Widget
profile_dict    = stm16_profile.profile_dict
