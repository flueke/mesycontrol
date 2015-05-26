#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import re
from .. qt import pyqtSignal
from .. qt import pyqtSlot
from .. qt import Qt
from .. qt import QtGui

from .. util import make_title_label, hline, make_spinbox
from .. import app_model
from .. import util

def group_channel_range(group_num):
    """Returns the range of channel indexes in the given channel group.
    group_num is the 0-based index of the channel group.
    """
    channels_per_group = STM16.num_channels / STM16.num_groups
    return xrange(group_num * channels_per_group, (group_num+1) * channels_per_group)

class STM16(app_model.Device):
    idcs = (19,)
    num_channels        = 16        # number of channels
    num_groups          = 8         # number of channel groups
    gain_factor         = 1.22      # gain step factor
    gain_adjust_limits  = (1, 100)  # limits of the hardware gain jumper inputs

    gain_changed        = pyqtSignal(object)
    threshold_changed   = pyqtSignal(object)
    gain_adjust_changed = pyqtSignal(int)  # gain adjust

    def __init__(self, device_model=None, device_config=None, device_profile=None, parent=None):
        super(STM16, self).__init__(device_model=device_model, device_config=device_config,
                device_profile=device_profile, parent=parent)

        self.log = util.make_logging_source_adapter(__name__, self)
        self._gain_adjust = 1
        self.parameter_changed[object].connect(self._on_parameter_changed)

    def propagate_state(self):
        """Propagate the current state using the signals defined in this class."""
        if not self.has_model():
            return

        for param_profile in self.profile.parameters:
            if self.has_parameter(param_profile.address):
                bp = self.make_bound_parameter(param_profile.address)
                self._on_parameter_changed(bp)
                self.parameter_changed[object].emit(bp)

    def _on_parameter_changed(self, bp):
        if bp.name is not None:
            if re.match(r"gain_group\d+", bp.name):
                self.gain_changed.emit(bp)

            elif re.match(r"threshold_channel\d+", bp.name):
                self.threshold_changed.emit(bp)

    def set_gain(self, group, value, response_handler=None):
        return self.set_parameter('gain_group%d' % group, value, response_handler=response_handler)

    def set_threshold(self, channel, value, response_handler=None):
        return self.set_parameter('threshold_channel%d' % channel, value,  response_handler=response_handler)

    def get_gain_adjust(self):
        return self._gain_adjust

    def set_gain_adjust(self, value):
        self._gain_adjust = int(value)
        self.gain_adjust_changed.emit(self.get_gain_adjust())

    gain_adjust = property(get_gain_adjust, set_gain_adjust)

    def get_total_gain(self, group):
        return STM16.gain_factor ** self['gain_group%d' % group] * self.get_gain_adjust()

    def get_extensions(self):
        return [('gain_adjust', self.gain_adjust)]

dynamic_label_style = "QLabel { background-color: lightgrey; }"

class GainPage(QtGui.QGroupBox):
    def __init__(self, device, parent=None):
        super(GainPage, self).__init__("Gain", parent)
        self.device         = device
        device.gain_changed.connect(self._on_device_gain_changed)
        device.gain_adjust_changed.connect(self._on_device_gain_adjust_changed)

        self.gain_inputs   = list()
        self.gain_labels   = list()
        self.hw_gain_input = None

        gain_min_max = device.profile['gain_group0'].range.to_tuple()

        layout = QtGui.QGridLayout(self)

        #layout.addWidget(QtGui.QLabel("Common"), 0, 0, 1, 1, Qt.AlignRight)
        #self.gain_common = make_spinbox(limits=gain_min_max)
        #self.gain_common.valueChanged[int].connect(self._on_gain_input_value_changed)
        #layout.addWidget(self.gain_common, 0, 1)

        layout.addWidget(make_title_label("Group"),   1, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("RC Gain"), 1, 1, 1, 1, Qt.AlignCenter)
        layout.addWidget(make_title_label("Total"),   1, 2, 1, 1, Qt.AlignCenter)

        offset = layout.rowCount()

        for i in range(STM16.num_groups):
            group_range = group_channel_range(i)
            descr_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1]))

            gain_spin   = make_spinbox(limits=gain_min_max)
            gain_spin.valueChanged[int].connect(self._on_gain_input_value_changed)

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

        self.hw_gain_input = make_spinbox(limits=STM16.gain_adjust_limits)
        self.hw_gain_input.setValue(device.get_gain_adjust())
        self.hw_gain_input.valueChanged[int].connect(self._on_hw_gain_input_value_changed)

        layout.addWidget(self.hw_gain_input, offset, 1)

    @pyqtSlot(int)
    def _on_gain_input_value_changed(self, value):
        s = self.sender()
        #if s == self.gain_common:
        #    self.device.set_common_gain(value)
        #else:
        g = self.gain_inputs.index(s)
        self.device.set_gain(g, value)

    @pyqtSlot(int)
    def _on_hw_gain_input_value_changed(self, value):
        self.device.set_gain_adjust(value)

    def _on_device_gain_changed(self, bp):
        spin = self.gain_common if not bp.has_index() else self.gain_inputs[bp.index]
        with util.block_signals(spin):
            spin.setValue(bp.value)
        if bp.has_index():
            self._update_gain_label(bp.index)

    def _on_device_gain_adjust_changed(self, value):
        with util.block_signals(self.hw_gain_input):
            self.hw_gain_input.setValue(value)

        for i in range(STM16.num_groups):
            self._update_gain_label(i)

    def _update_gain_label(self, group):
        self.gain_labels[group].setText("%.1f" % self.device.get_total_gain(group))

class TimingPage(QtGui.QGroupBox):
    def __init__(self, device, parent=None):
        super(TimingPage, self).__init__("Timing", parent)
        self.device           = device
        self.device.threshold_changed.connect(self._on_device_threshold_changed)

        #self.threshold_common = make_spinbox(limits=device.profile['threshold_common'].range.to_tuple())
        self.threshold_inputs = list()
        self.threshold_labels = list()

        #self.threshold_common.valueChanged[int].connect(self._on_threshold_changed)

        layout = QtGui.QGridLayout(self)

        #layout.addWidget(QtGui.QLabel("Common"), 0, 0, 1, 1, Qt.AlignRight)
        #layout.addWidget(self.threshold_common, 0, 1)

        layout.addWidget(make_title_label("Channel"),   1, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Threshold"), 1, 1)

        for chan in range(STM16.num_channels):
            offset  = 2
            descr_label     = QtGui.QLabel("%d" % chan)
            spin_threshold  = QtGui.QSpinBox()
            spin_threshold  = make_spinbox(limits=device.profile['threshold_channel0'].range.to_tuple())
            label_threshold = QtGui.QLabel()
            label_threshold.setStyleSheet(dynamic_label_style)

            layout.addWidget(descr_label,       chan+offset, 0, 1, 1, Qt.AlignRight)
            layout.addWidget(spin_threshold,    chan+offset, 1)
            layout.addWidget(label_threshold,   chan+offset, 2)

            self.threshold_inputs.append(spin_threshold)
            self.threshold_labels.append(label_threshold)
            spin_threshold.valueChanged[int].connect(self._on_threshold_changed)

    @pyqtSlot(int)
    def _on_threshold_changed(self, value):
        s = self.sender()
        #if s == self.threshold_common:
        #    self.device.set_common_threshold(value)
        #else:
        c = self.threshold_inputs.index(s)
        self.device.set_threshold(c, value)

    def _on_device_threshold_changed(self, bp):
        spin = self.threshold_inputs[bp.index]
        with util.block_signals(spin):
            spin.setValue(bp.value)
        l = self.threshold_labels[bp.index]
        l.setText("%.1f%%" % self.device.get_parameter_by_name("threshold_channel%d" % bp.index, 'percent'))

class STM16Widget(QtGui.QWidget):
    def __init__(self, device, context, parent=None):
        super(STM16Widget, self).__init__(parent)
        self.context = context
        self.device  = device
        self.device.add_default_parameter_subscription(self)

        self.gain_page   = GainPage(device, self)
        self.timing_page = TimingPage(device, self)

        pages = [self.gain_page, self.timing_page]

        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(*(4 for i in range(4)))
        layout.setSpacing(4)

        for page in pages:
            vbox = QtGui.QVBoxLayout()
            vbox.addWidget(page)
            vbox.addStretch(1)
            layout.addItem(vbox)

        self.device.propagate_state()

idc             = 19
device_class    = STM16
device_ui_class = STM16Widget
