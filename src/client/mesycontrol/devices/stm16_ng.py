#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from .. qt import pyqtSlot
from .. qt import Qt
from .. qt import QtGui

from .. device import Device
from .. import future
from .. import parameter_binding as pb
from .. import util
from .. util import hline
from .. util import make_spinbox
from .. util import make_title_label

NUM_CHANNELS        = 16        # number of channels
NUM_GROUPS          =  8        # number of channel groups
GAIN_FACTOR         = 1.22      # gain step factor
GAIN_ADJUST_LIMITS  = (1, 100)  # limits of the hardware gain jumpers

cg_helper = util.ChannelGroupHelper(NUM_CHANNELS, NUM_GROUPS)

class STM16(Device):
    def __init__(self, app_device, read_mode, write_mode, parent=None):
        super(STM16, self).__init__(app_device, read_mode, write_mode, parent)

    def get_gain_adjust(self):
        obj = self.cfg if self.cfg is not None else self.profile
        return obj.get_extension('gain_adjust')

    def set_gain_adjust(self, gain_adjust):
        self.cfg.set_extension('gain_adjust', int(gain_adjust))

    def get_total_gain(self, group):
        ret = future.Future()
        def get_done(f):
            try:
                ret.set_result(GAIN_FACTOR ** int(f) * self.get_gain_adjust())
            except Exception as e:
                ret.set_exception(e)
        self.get_parameter('gain_group%d' % group).add_done_callback(get_done)
        return ret

dynamic_label_style = "QLabel { background-color: lightgrey; }"

class GainPage(QtGui.QGroupBox):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(GainPage, self).__init__("Gain", parent)
        self.device         = device

        #device.gain_changed.connect(self._on_device_gain_changed)
        #device.gain_adjust_changed.connect(self._on_device_gain_adjust_changed)

        self.gain_inputs   = list()
        self.gain_labels   = list()
        self.hw_gain_input = None
        self.bindings = list()

        #gain_min_max = device.profile['gain_group0'].range.to_tuple()

        layout = QtGui.QGridLayout(self)

        #layout.addWidget(QtGui.QLabel("Common"), 0, 0, 1, 1, Qt.AlignRight)
        #self.gain_common = make_spinbox(limits=gain_min_max)
        #self.gain_common.valueChanged[int].connect(self._on_gain_input_value_changed)
        #layout.addWidget(self.gain_common, 0, 1)

        layout.addWidget(make_title_label("Group"),   1, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("RC Gain"), 1, 1, 1, 1, Qt.AlignCenter)
        layout.addWidget(make_title_label("Total"),   1, 2, 1, 1, Qt.AlignCenter)

        offset = layout.rowCount()

        for i in range(NUM_GROUPS):
            group_range = cg_helper.group_channel_range(i)
            descr_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1]))
            gain_spin   = util.DelayedSpinBox()
            self.bindings.append(pb.factory.make_binding(
                device=device,
                profile=self.device.profile['gain_group%d' % i],
                display_mode=display_mode,
                write_mode=write_mode,
                target=gain_spin))

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

    #def _on_device_gain_adjust_changed(self, value):
    #    with util.block_signals(self.hw_gain_input):
    #        self.hw_gain_input.setValue(value)

    #    for i in range(STM16.num_groups):
    #        self._update_gain_label(i)
    # => use extension mechanism

    #def _update_gain_label(self, group):
    #    self.gain_labels[group].setText("%.1f" % self.device.get_total_gain(group))

class TimingPage(QtGui.QGroupBox):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(TimingPage, self).__init__("Timing", parent)
        self.device           = device
        #self.device.threshold_changed.connect(self._on_device_threshold_changed)

        #self.threshold_common = make_spinbox(limits=device.profile['threshold_common'].range.to_tuple())
        self.threshold_inputs = list()
        self.threshold_labels = list()
        self.bindings = list()

        #self.threshold_common.valueChanged[int].connect(self._on_threshold_changed)

        layout = QtGui.QGridLayout(self)

        #layout.addWidget(QtGui.QLabel("Common"), 0, 0, 1, 1, Qt.AlignRight)
        #layout.addWidget(self.threshold_common, 0, 1)

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


    #@pyqtSlot(int)
    #def _on_threshold_changed(self, value):
    #    s = self.sender()
    #    #if s == self.threshold_common:
    #    #    self.device.set_common_threshold(value)
    #    #else:
    #    c = self.threshold_inputs.index(s)
    #    self.device.set_threshold(c, value)

    #def _on_device_threshold_changed(self, bp):
    #    spin = self.threshold_inputs[bp.index]
    #    with util.block_signals(spin):
    #        spin.setValue(bp.value)
    #    l = self.threshold_labels[bp.index]
    #    l.setText("%.1f%%" % self.device.get_parameter_by_name("threshold_channel%d" % bp.index, 'percent'))

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

    def set_display_mode(self, display_mode):
        for page in self.pages:
            for binding in page.bindings:
                binding.set_display_mode(display_mode)

    def set_write_mode(self, write_mode):
        for page in self.pages:
            for binding in page.bindings:
                binding.set_write_mode(write_mode)

idc = 19
device_class    = STM16
device_ui_class = STM16Widget
