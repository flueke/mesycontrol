#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import collections

from .. qt import pyqtSlot
from .. qt import Qt
from .. qt import QtCore
from .. qt import QtGui

from .. future import set_exception_on
from .. future import set_result_on
from .. import future
from .. import parameter_binding as pb
from .. import util
from .. specialized_device import DeviceBase
from .. util import hline
from .. util import make_spinbox
from .. util import make_title_label

import device_profile_mscf16

NUM_CHANNELS        = 16        # number of channels
NUM_GROUPS          =  4        # number of channel groups
GAIN_FACTOR         = 1.22      # gain step factor
GAIN_ADJUST_LIMITS  = (1, 100)  # limits of the hardware gain jumpers

cg_helper = util.ChannelGroupHelper(NUM_CHANNELS, NUM_GROUPS)

class ModuleInfo(object):
    """Holds information about an MSCF16 that can't be detected via
    software."""
    shaping_times_us = {
            1: [0.125, 0.25, 0.5, 1.0],
            2: [0.25,  0.5,  1.0, 2.0],
            4: [0.5,   1.0,  2.0, 4.0],
            8: [1.0,   2.0,  4.0, 8.0]
            }

    def __init__(self, name='F', shaping_time=1, input_type='V',
            input_connector='L', discriminator='CFD', cfd_delay=30):
        self.name               = name
        self.shaping_time       = shaping_time
        self.input_type         = input_type
        self.input_connector    = input_connector
        self.discriminator      = discriminator
        self.cfd_delay          = cfd_delay

class HardwareInfo(object):
    """Decodes the `hardware_info' register of newer MSCF16s."""
    LN_TYPE         = 1 << 0
    HW_GE_V4        = 1 << 1
    INTEGRATING     = 1 << 2
    SUMDIS          = 1 << 6

    def __init__(self, hw_info):
        self.info = hw_info

    def is_ln_type(self):
        """True if LN (low noise) version"""
        return self.info & HardwareInfo.LN_TYPE

    def is_hw_version_ge_4(self):
        """True if hardware version >= 4"""
        return self.info & HardwareInfo.HW_GE_V4

    def is_integrating(self):
        """True if this is a charge integrating MSCF16 (PMT variant)"""
        return self.info & HardwareInfo.INTEGRATING

    def has_sumdis(self):
        return self.info & HardwareInfo.SUMDIS

class CopyFunction(object):
    panel2rc        = 1
    rc2panel        = 2
    common2single   = 3

Version = collections.namedtuple('major minor')

def version_to_major_minor(version):
   minor = version % 16;
   major = (version - minor) / 16;

   return (major, minor)

def get_config_parameters(app_device):
    # TODO
    return future.Future().set_result([])

# ==========  Device ========== 
class MSCF16(DeviceBase):
    def __init__(self, app_device, read_mode, write_mode, parent=None):
        super(MSCF16, self).__init__(app_device, read_mode, write_mode, parent)
        self.log = util.make_logging_source_adapter(__name__, self)

        self._auto_pz_channel = 0
        self._gain_adjusts    = [1 for i in range(MSCF16.num_groups)]
        self.module_info      = ModuleInfo()

    def perform_copy_function(self, copy_function):
        """Performs one of the MSCF copy functions as defined in CopyFunction.
        After writing the copy_function register all parameters are re-read
        from the hardware.
        Returns a Future.
        """
        futures = [self.set_hw_parameter('copy_function', copy_function)]

        for p in self.profile.parameters:
            futures.append(self.read_hw_parameter(p.address))

        return future.all_done(*futures)

    def get_software_version(self):
        """Reads the 'version' register and returns a Future whose result is a
        tuple of the form (major, minor)."""

        ret = future.Future()

        @set_result_on(ret)
        def done(f):
            return Version(divmod(int(f), 16))

        self.get_hw_parameter('version').add_done_callback(done)

        return ret

    def has_detailed_versions(self):
        ret = future.Future()

        @set_result_on(ret)
        def done(f):
            version = f.result()
            return version.major >= 5 and version.minor >= 3

        self.get_software_version().add_done_callback(done)

        return ret

    def get_fpga_version(self):
        ret = future.Future()

        @set_result_on(ret)
        def fpga_version_done(f):
            return Version(divmod(int(f), 256))

        @set_exception_on(ret)
        def has_versions_done(f):
            if f.result():
                self.get_parameter('fpga_version').add_done_callback(fpga_version_done)
            else:
                raise RuntimeError("FPGA version info not supported")

        self.has_detailed_versions().add_done_callback(has_versions_done)

        return ret

# ==========  GUI ========== 
dynamic_label_style = "QLabel { background-color: lightgrey; }"

class MSCF16Widget(QtGui.QWidget):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(MSCF16Widget, self).__init__(parent)
        self.device = device

        self.gain_page      = GainPage(device, display_mode, write_mode, self)
        self.shaping_page   = ShapingPage(device, display_mode, write_mode, self)
        self.timing_page    = TimingPage(device, display_mode, write_mode, self)
        self.misc_page      = MiscPage(device, display_mode, write_mode, self)

        pages = [self.gain_page, self.shaping_page, self.timing_page, self.misc_page]

        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(*(4 for i in range(4)))
        layout.setSpacing(4)

        for page in pages:
            vbox = QtGui.QVBoxLayout()
            vbox.addWidget(page)
            vbox.addStretch(1)
            layout.addItem(vbox)

def make_apply_common_button_layout(input_spinbox, tooltip, on_clicked, context):
    button = QtGui.QPushButton(clicked=on_clicked)
    button.setIcon(QtGui.QIcon(context.find_data_file('mesycontrol/ui/arrow-bottom-2x.png')))
    button.setMaximumHeight(input_spinbox.sizeHint().height())
    button.setMaximumWidth(16)
    button.setToolTip(tooltip)

    layout = QtGui.QHBoxLayout()
    layout.addWidget(input_spinbox)
    layout.addWidget(button)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(1)

    return (layout, button)

class GainPage(QtGui.QGroupBox):
    def __init__(self, device, context, parent=None):
        super(GainPage, self).__init__("Gain", parent)
        self.device         = device
        device.gain_changed.connect(self._on_device_gain_changed)
        device.gain_adjust_changed.connect(self._on_device_gain_adjust_changed)

        self.gain_inputs    = list()
        self.gain_labels    = list()
        self.hw_gain_inputs = list()

        gain_min_max = device.profile['gain_common'].range.to_tuple()

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(QtGui.QLabel("Common"), 0, 0, 1, 1, Qt.AlignRight)

        self.gain_common = make_spinbox(limits=gain_min_max)
        self.gain_common.valueChanged[int].connect(self._on_gain_input_value_changed)

        common_layout = make_apply_common_button_layout(
                self.gain_common, "Apply to groups", self._apply_common_gain, context)[0]
        layout.addLayout(common_layout, 0, 1)

        layout.addWidget(make_title_label("Group"),   1, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("RC Gain"), 1, 1, 1, 1, Qt.AlignCenter)
        layout.addWidget(make_title_label("Total"),   1, 2, 1, 1, Qt.AlignCenter)

        offset = layout.rowCount()

        for i in range(MSCF16.num_groups):
            group_range = cg_helper.group_channel_range(i)
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

        layout.addWidget(make_title_label("Gain Jumpers"), layout.rowCount(), 0, 1, 3, Qt.AlignCenter)

        offset = layout.rowCount()

        for i in range(MSCF16.num_groups):
            group_range = cg_helper.group_channel_range(i)
            descr_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1]))
            gain_spin   = make_spinbox(limits=MSCF16.gain_adjust_limits)
            gain_spin.setValue(device.get_gain_adjust(i))
            gain_spin.valueChanged[int].connect(self._on_hw_gain_input_value_changed)

            self.hw_gain_inputs.append(gain_spin)

            layout.addWidget(descr_label, i+offset, 0, 1, 1, Qt.AlignRight)
            layout.addWidget(gain_spin,   i+offset, 1)

    def _apply_common_gain(self):
        raise NotImplementedError()
        #cmd = command.SequentialCommandGroup()
        #for i in range(MSCF16.num_groups):
        #    set_cmd = mrc_command.SetParameter(self.device, 'gain_group%d' % i, self.device['gain_common'])
        #    cmd.add(set_cmd)

        #d = command.CommandProgressDialog(cmd, cancelButtonText=QtCore.QString(), parent=self)
        #d.exec_()

    @pyqtSlot(int)
    def _on_gain_input_value_changed(self, value):
        s = self.sender()
        if s == self.gain_common:
            self.device.set_common_gain(value)
        else:
            g = self.gain_inputs.index(s)
            self.device.set_gain(g, value)

    @pyqtSlot(int)
    def _on_hw_gain_input_value_changed(self, value):
        s = self.sender()
        g = self.hw_gain_inputs.index(s)
        self.device.set_gain_adjust(g, value)

    def _on_device_gain_changed(self, bp):
        spin = self.gain_common if not bp.has_index() else self.gain_inputs[bp.index]
        with util.block_signals(spin):
            spin.setValue(bp.value)
        if bp.has_index():
            self._update_gain_label(bp.index)

    def _on_device_gain_adjust_changed(self, group, value):
        spin = self.hw_gain_inputs[group]
        with util.block_signals(spin):
            spin.setValue(value)
        self._update_gain_label(group)

    def _update_gain_label(self, group):
        self.gain_labels[group].setText("%.1f" % self.device.get_total_gain(group))

class AutoPZSpin(QtGui.QStackedWidget):
    def __init__(self, limits=None, parent=None):
        super(AutoPZSpin, self).__init__(parent)

        self.spin     = make_spinbox(limits=limits)
        self.progress = QtGui.QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)
        # Ignore the size hint of the progressbar so that only the size of the
        # spinbox is taken into account when calculating the final widget size.
        self.progress.setSizePolicy(QtGui.QSizePolicy.Ignored, QtGui.QSizePolicy.Ignored)

        self.addWidget(self.spin)
        self.addWidget(self.progress)

    def showSpin(self):
        self.setCurrentIndex(0)

    def showProgress(self):
        self.setCurrentIndex(1)

class ShapingPage(QtGui.QGroupBox):
    auto_pz_button_size = QtCore.QSize(24, 24)

    def __init__(self, device, context, parent=None):
        super(ShapingPage, self).__init__("Shaping", parent)
        self.device = device
        self.device.shaping_time_changed.connect(self._on_device_shaping_time_changed)
        self.device.pz_value_changed.connect(self._on_device_pz_value_changed)
        self.device.shaper_offset_changed.connect(self._on_device_shaper_offset_changed)
        self.device.blr_threshold_changed.connect(self._on_device_blr_threshold_changed)
        self.device.blr_changed.connect(self._on_device_blr_changed)
        self.device.auto_pz_channel_changed.connect(self._on_device_auto_pz_channel_changed)
        self.device.module_info_changed.connect(self._on_device_module_info_changed)

        self.stop_icon  = QtGui.QIcon(context.find_data_file('mesycontrol/ui/process-stop.png'))
        self.sht_inputs = list()
        self.sht_labels = list()
        self.pz_inputs  = list()
        self.pz_buttons = list()
        self.pz_stacks  = list()

        shaping_time_limits = device.profile['shaping_time_common'].range.to_tuple()
        pz_value_limits     = device.profile['pz_value_common'].range.to_tuple()

        # Columns: group_num, shaping time input, shaping time display, chan_num, pz input, auto pz button

        self.spin_sht_common    = make_spinbox(limits=shaping_time_limits)
        self.spin_sht_common.valueChanged[int].connect(self._on_shaping_time_value_changed)

        self.spin_pz_common     = make_spinbox(limits=pz_value_limits)
        self.spin_pz_common.valueChanged[int].connect(self._on_pz_value_changed)

        sht_common_layout = make_apply_common_button_layout(
                self.spin_sht_common, "Apply to groups", self._apply_common_sht, context)[0]

        pz_common_layout  = make_apply_common_button_layout(
                self.spin_pz_common, "Apply to channels", self._apply_common_pz, context)[0]

        self.pb_auto_pz_all  = QtGui.QPushButton("A")
        self.pb_auto_pz_all.setToolTip("Start auto PZ for all channels")
        self.pb_auto_pz_all.setStatusTip(self.pb_auto_pz_all.toolTip())
        self.pb_auto_pz_all.setMaximumSize(ShapingPage.auto_pz_button_size)
        self.pb_auto_pz_all.clicked.connect(self._on_auto_pz_button_clicked)

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(QtGui.QLabel("Common"),    0, 0, 1, 1, Qt.AlignRight)
        layout.addLayout(sht_common_layout,         0, 1)
        layout.addWidget(QtGui.QLabel("Common"),    0, 3, 1, 1, Qt.AlignRight)
        layout.addLayout(pz_common_layout,          0, 4)
        layout.addWidget(self.pb_auto_pz_all,       0, 5)

        layout.addWidget(make_title_label("Group"),         1, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Shaping time"),  1, 1, 1, 2, Qt.AlignCenter)
        layout.addWidget(make_title_label("Chan"),       1, 3)
        layout.addWidget(make_title_label("PZ"),            1, 4)

        for chan in range(MSCF16.num_channels):
            group = int(chan / MSCF16.num_groups)
            group_range = cg_helper.group_channel_range(group)
            row   = layout.rowCount()

            if chan % MSCF16.num_groups == 0:
                descr_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1]))
                spin_sht    = make_spinbox(limits=shaping_time_limits)
                label_sht   = QtGui.QLabel("N/A")
                label_sht.setStyleSheet(dynamic_label_style)

                layout.addWidget(descr_label,   row, 0, 1, 1, Qt.AlignRight)
                layout.addWidget(spin_sht,      row, 1)
                layout.addWidget(label_sht,     row, 2)

                self.sht_inputs.append(spin_sht)
                self.sht_labels.append(label_sht)
                spin_sht.valueChanged[int].connect(self._on_shaping_time_value_changed)

            label_chan  = QtGui.QLabel("%d" % chan)
            spin_pz     = AutoPZSpin(limits=pz_value_limits)
            spin_pz.spin.valueChanged[int].connect(self._on_pz_value_changed)
            self.pz_inputs.append(spin_pz.spin)
            self.pz_stacks.append(spin_pz)

            button_pz   = QtGui.QPushButton("A")
            button_pz.setToolTip("Start auto PZ for channel %d" % chan)
            button_pz.setMaximumSize(ShapingPage.auto_pz_button_size)
            button_pz.clicked.connect(self._on_auto_pz_button_clicked)
            self.pz_buttons.append(button_pz)

            layout.addWidget(label_chan,    row, 3, 1, 1, Qt.AlignRight)
            layout.addWidget(spin_pz,       row, 4)
            layout.addWidget(button_pz,     row, 5)


        layout.addWidget(hline(), layout.rowCount(), 0, 1, 6)

        self.spin_shaper_offset = make_spinbox(limits=device.profile['shaper_offset'].range.to_tuple())
        self.spin_blr_threshold = make_spinbox(limits=device.profile['blr_threshold'].range.to_tuple())
        self.check_blr_enable   = QtGui.QCheckBox()

        self.spin_shaper_offset.valueChanged[int].connect(self._on_shaper_offset_value_changed)
        self.spin_blr_threshold.valueChanged[int].connect(self._on_blr_threshold_value_changed)
        self.check_blr_enable.clicked[bool].connect(self._on_blr_enable_clicked)

        row = layout.rowCount()
        layout.addWidget(QtGui.QLabel("Sh. offset"), row, 0)
        layout.addWidget(self.spin_shaper_offset, row, 1)

        row += 1
        layout.addWidget(QtGui.QLabel("BLR thresh."), row, 0)
        layout.addWidget(self.spin_blr_threshold, row, 1)

        row += 1
        layout.addWidget(QtGui.QLabel("BLR enable"), row, 0)
        layout.addWidget(self.check_blr_enable, row, 1)

    # ===== GUI changes =====

    @pyqtSlot(int)
    def _on_shaping_time_value_changed(self, value):
        s = self.sender()
        if s == self.spin_sht_common:
            self.device.set_common_shaping_time(value)
        else:
            g = self.sht_inputs.index(s)
            self.device.set_shaping_time(g, value)

    @pyqtSlot(int)
    def _on_pz_value_changed(self, value):
        s = self.sender()
        if s == self.spin_pz_common:
            self.device.set_common_pz_value(value)
        else:
            c = self.pz_inputs.index(s)
            self.device.set_pz_value(c, value)

    @pyqtSlot(int)
    def _on_shaper_offset_value_changed(self, value):
        self.device.set_shaper_offset(value)

    @pyqtSlot(int)
    def _on_blr_threshold_value_changed(self, value):
        self.device.set_blr_threshold(value)

    @pyqtSlot(bool)
    def _on_blr_enable_clicked(self, checked):
        self.device.set_blr(checked)

    @pyqtSlot()
    def _on_auto_pz_button_clicked(self):
        s = self.sender()
        if s == self.pb_auto_pz_all:
            self.device.set_auto_pz_channel(17)
        else:
            idx = self.pz_buttons.index(s)
            if self.device.get_auto_pz_channel() == idx+1:
                self.device.set_auto_pz_channel(0)
            else:
                self.device.set_auto_pz_channel(idx+1)

    def _apply_common_sht(self):
        raise NotImplementedError()
    #    cmd = command.SequentialCommandGroup()
    #    for i in range(MSCF16.num_groups):
    #        set_cmd = mrc_command.SetParameter(self.device, 'shaping_time_group%d' % i,
    #                self.device['shaping_time_common'])
    #        cmd.add(set_cmd)

    #    d = command.CommandProgressDialog(cmd, cancelButtonText=QtCore.QString(), parent=self)
    #    d.exec_()

    def _apply_common_pz(self):
        raise NotImplementedError()
    #    cmd = command.SequentialCommandGroup()
    #    for i in range(MSCF16.num_channels):
    #        set_cmd = mrc_command.SetParameter(self.device, 'pz_value_channel%d' % i,
    #                self.device['pz_value_common'])
    #        cmd.add(set_cmd)

    #    d = command.CommandProgressDialog(cmd, cancelButtonText=QtCore.QString(), parent=self)
    #    d.exec_()


    # ===== Device changes =====
    def _on_device_shaping_time_changed(self, bp):
        spin = self.spin_sht_common if not bp.has_index() else self.sht_inputs[bp.index]
        with util.block_signals(spin):
            spin.setValue(bp.value)

        if bp.has_index():
            self._update_sht_label(bp.index)

    def _on_device_pz_value_changed(self, bp):
        spin = self.spin_pz_common if not bp.has_index() else self.pz_inputs[bp.index]
        with util.block_signals(spin):
            spin.setValue(bp.value)

    def _on_device_shaper_offset_changed(self, value):
        with util.block_signals(self.spin_shaper_offset):
            self.spin_shaper_offset.setValue(value)

    def _on_device_blr_threshold_changed(self, value):
        with util.block_signals(self.spin_blr_threshold):
            self.spin_blr_threshold.setValue(value)

    def _on_device_blr_changed(self, on_off):
        with util.block_signals(self.check_blr_enable):
            self.check_blr_enable.setChecked(on_off)

    def _on_device_auto_pz_channel_changed(self, value):
        for i, pz_stack in enumerate(self.pz_stacks):
            if value == 0 or i != value-1:
                pz_stack.showSpin()
                self.pz_buttons[i].setText("A")
                self.pz_buttons[i].setIcon(QtGui.QIcon())
                self.pz_buttons[i].setToolTip("Start auto PZ for channel %d" % i)
            elif i == value-1:
                pz_stack.showProgress()
                self.pz_buttons[i].setText("")
                self.pz_buttons[i].setIcon(self.stop_icon)
                self.pz_buttons[i].setToolTip("Stop auto PZ")

    def _on_device_module_info_changed(self, mod_info):
        for i in range(MSCF16.num_groups):
            self._update_sht_label(i)

    def _update_sht_label(self, group):
        text  = "%.2f µs" % self.device.get_effective_shaping_time(group)
        label = self.sht_labels[group]
        label.setText(QtCore.QString.fromUtf8(text))


class TimingPage(QtGui.QGroupBox):
    def __init__(self, device, context, parent=None):
        super(TimingPage, self).__init__("Timing", parent)
        self.device           = device
        self.device.threshold_changed.connect(self._on_device_threshold_changed)
        self.device.threshold_offset_changed.connect(self._on_device_threshold_offset_changed)
        self.device.ecl_delay_enable_changed.connect(self._on_device_ecl_enable_changed)
        self.device.tf_int_time_changed.connect(self._on_device_tf_int_time_changed)

        self.threshold_inputs = list()
        self.threshold_labels = list()

        self.threshold_common = make_spinbox(limits=device.profile['threshold_common'].range.to_tuple())
        self.threshold_common.valueChanged[int].connect(self._on_threshold_changed)

        threshold_common_layout = make_apply_common_button_layout(
                self.threshold_common, "Apply to channels", self._apply_common_threshold, context)[0]

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(QtGui.QLabel("Common"), 0, 0, 1, 1, Qt.AlignRight)
        layout.addLayout(threshold_common_layout, 0, 1)

        layout.addWidget(make_title_label("Chan"),   1, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Threshold"), 1, 1)

        for chan in range(MSCF16.num_channels):
            offset  = 2
            descr_label     = QtGui.QLabel("%d" % chan)
            spin_threshold  = QtGui.QSpinBox()
            spin_threshold  = make_spinbox(limits=device.profile['threshold_common'].range.to_tuple())
            label_threshold = QtGui.QLabel()
            label_threshold.setStyleSheet(dynamic_label_style)

            layout.addWidget(descr_label,       chan+offset, 0, 1, 1, Qt.AlignRight)
            layout.addWidget(spin_threshold,    chan+offset, 1)
            layout.addWidget(label_threshold,   chan+offset, 2)

            self.threshold_inputs.append(spin_threshold)
            self.threshold_labels.append(label_threshold)
            spin_threshold.valueChanged[int].connect(self._on_threshold_changed)

        layout.addWidget(hline(), layout.rowCount(), 0, 1, 3)

        self.spin_threshold_offset = make_spinbox(limits=device.profile['threshold_offset'].range.to_tuple())
        self.spin_threshold_offset.valueChanged[int].connect(self._on_threshold_offset_changed)

        self.check_ecl_delay = QtGui.QCheckBox()
        self.check_ecl_delay.clicked[bool].connect(self._on_check_ecl_delay_clicked)

        self.spin_tf_int_time = make_spinbox(limits=device.profile['tf_int_time'].range.to_tuple())
        self.spin_tf_int_time.valueChanged[int].connect(self._on_tf_int_time_changed)

        row = layout.rowCount()
        layout.addWidget(QtGui.QLabel("Thr. offset"),   row, 0)
        layout.addWidget(self.spin_threshold_offset,    row, 1)

        row += 1
        layout.addWidget(QtGui.QLabel("ECL delay"),     row, 0)
        layout.addWidget(self.check_ecl_delay,          row, 1)

        row += 1
        layout.addWidget(QtGui.QLabel("TF int. time"),  row, 0)
        layout.addWidget(self.spin_tf_int_time,         row, 1)

    @pyqtSlot(int)
    def _on_threshold_changed(self, value):
        s = self.sender()
        if s == self.threshold_common:
            self.device.set_common_threshold(value)
        else:
            c = self.threshold_inputs.index(s)
            self.device.set_threshold(c, value)

    @pyqtSlot(int)
    def _on_threshold_offset_changed(self, value):
        self.device.set_threshold_offset(value)

    @pyqtSlot(int)
    def _on_check_ecl_delay_clicked(self, on_off):
        self.device.set_ecl_delay_enable(on_off)

    @pyqtSlot(int)
    def _on_tf_int_time_changed(self, value):
        self.device.set_tf_int_time(value)

    def _apply_common_threshold(self):
        raise NotImplementedError()
        #cmd = command.SequentialCommandGroup()
        #for i in range(MSCF16.num_channels):
        #    set_cmd = mrc_command.SetParameter(self.device, 'threshold_channel%d' % i,
        #            self.device['threshold_common'])
        #    cmd.add(set_cmd)

        #d = command.CommandProgressDialog(cmd, cancelButtonText=QtCore.QString(), parent=self)
        #d.exec_()


    def _on_device_threshold_changed(self, bp):
        spin = self.threshold_common if not bp.has_index() else self.threshold_inputs[bp.index]
        with util.block_signals(spin):
            spin.setValue(bp.value)
        if bp.has_index():
            l = self.threshold_labels[bp.index]
            l.setText("%.1f%%" % self.device.get_parameter_by_name("threshold_channel%d" % bp.index, 'percent'))

    def _on_device_threshold_offset_changed(self, value):
        with util.block_signals(self.spin_threshold_offset):
            self.spin_threshold_offset.setValue(value)

    def _on_device_ecl_enable_changed(self, on_off):
        if not self.device.has_feature('ecl_delay_enable'):
            self.check_ecl_delay.setEnabled(False)
            self.check_ecl_delay.setToolTip("N/A")
        with util.block_signals(self.check_ecl_delay):
            self.check_ecl_delay.setChecked(on_off if self.device.has_feature('ecl_delay_enable') else True)

    def _on_device_tf_int_time_changed(self, value):
        if not self.device.has_feature('tf_int_time'):
            self.spin_tf_int_time.setEnabled(False)
            self.spin_tf_int_time.setToolTip("N/A")
        with util.block_signals(self.spin_tf_int_time):
            self.spin_tf_int_time.setValue(value if self.device.has_feature('tf_int_time') else 0)

class MiscPage(QtGui.QWidget):
    def __init__(self, device, parent=None):
        super(MiscPage, self).__init__(parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self.device = device
        self.device.coincidence_time_changed.connect(self._on_device_coincidence_time_changed)
        self.device.multiplicity_low_changed.connect(self._on_device_multiplicity_low_changed)
        self.device.multiplicity_high_changed.connect(self._on_device_multiplicity_high_changed)
        self.device.monitor_channel_changed.connect(self._on_device_monitor_channel_changed)
        self.device.single_channel_mode_changed.connect(self._on_device_single_channel_mode_changed)
        self.device.parameter_changed[object].connect(self._on_device_parameter_changed)

        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Coincidence/Trigger
        trigger_box = QtGui.QGroupBox("Coincidence/Trigger")
        trigger_layout = QtGui.QGridLayout(trigger_box)
        trigger_layout.setContentsMargins(2, 2, 2, 2)

        self.spin_coincidence_time  = make_spinbox(limits=device.profile['coincidence_time'].range.to_tuple())
        self.spin_multiplicity_high = make_spinbox(limits=device.profile['multiplicity_hi'].range.to_tuple())
        self.spin_multiplicity_low  = make_spinbox(limits=device.profile['multiplicity_lo'].range.to_tuple())

        self.spin_coincidence_time.valueChanged[int].connect(self._coincidence_time_changed)
        self.spin_multiplicity_low.valueChanged[int].connect(self._mult_lo_changed)
        self.spin_multiplicity_high.valueChanged[int].connect(self._mult_hi_changed)

        self.label_coincidence_time = QtGui.QLabel()
        self.label_coincidence_time.setStyleSheet(dynamic_label_style)

        row = 0
        trigger_layout.addWidget(QtGui.QLabel("Coinc. time"), row, 0)
        trigger_layout.addWidget(self.spin_coincidence_time,  row, 1)
        trigger_layout.addWidget(self.label_coincidence_time, row, 2)

        row += 1
        trigger_layout.addWidget(QtGui.QLabel("Mult. low"),   row, 0)
        trigger_layout.addWidget(self.spin_multiplicity_low, row, 1)

        row += 1
        trigger_layout.addWidget(QtGui.QLabel("Mult. high"),   row, 0)
        trigger_layout.addWidget(self.spin_multiplicity_high, row, 1)

        # Monitor
        monitor_box = QtGui.QGroupBox("Monitor Channel")
        monitor_layout = QtGui.QGridLayout(monitor_box)
        monitor_layout.setContentsMargins(2, 2, 2, 2)
        self.combo_monitor  = QtGui.QComboBox()
        self.combo_monitor.addItem("Off")
        self.combo_monitor.addItems(["Channel %d" % i for i in range(MSCF16.num_channels)])
        self.combo_monitor.setMaxVisibleItems(MSCF16.num_channels+1)
        self.combo_monitor.currentIndexChanged[int].connect(self._monitor_channel_selected)
        monitor_layout.addWidget(self.combo_monitor, 0, 0)

        # Channel mode
        mode_box = QtGui.QGroupBox("Channel Mode")
        mode_layout = QtGui.QGridLayout(mode_box)
        mode_layout.setContentsMargins(2, 2, 2, 2)
        self.rb_mode_single = QtGui.QRadioButton("Single", toggled=self._rb_mode_single_toggled)
        self.rb_mode_common = QtGui.QRadioButton("Common")
        mode_layout.addWidget(self.rb_mode_single, 0, 0)
        mode_layout.addWidget(self.rb_mode_common, 0, 1)

        # Copy Functions
        copy_box = QtGui.QGroupBox("Copy")
        copy_layout = QtGui.QVBoxLayout(copy_box)
        copy_layout.setContentsMargins(2, 2, 2, 2)

        self.pb_copy_panel2rc           = QtGui.QPushButton("Panel -> RC", clicked=self._copy_panel2rc)
        self.copy_panel2rc_progress     = QtGui.QProgressBar()
        self.copy_panel2rc_stack        = QtGui.QStackedWidget()
        self.copy_panel2rc_stack.addWidget(self.pb_copy_panel2rc)
        self.copy_panel2rc_stack.addWidget(self.copy_panel2rc_progress)

        self.pb_copy_rc2panel               = QtGui.QPushButton("RC -> Panel", clicked=self._copy_rc2panel)

        self.pb_copy_common2single          = QtGui.QPushButton("Common -> Single", clicked=self._copy_common2single)
        self.copy_common2single_progress    = QtGui.QProgressBar()
        self.stack_copy_common2single       = QtGui.QStackedWidget()
        self.stack_copy_common2single.addWidget(self.pb_copy_common2single)
        self.stack_copy_common2single.addWidget(self.copy_common2single_progress)

        copy_layout.addWidget(self.copy_panel2rc_stack)
        copy_layout.addWidget(self.pb_copy_rc2panel)
        copy_layout.addWidget(self.stack_copy_common2single)

        # Version display
        version_box = QtGui.QGroupBox("Version")
        version_layout = QtGui.QFormLayout(version_box)
        version_layout.setContentsMargins(2, 2, 2, 2)

        self.version_labels = dict()
        for k in ("Software", "Hardware", "FPGA"):
            self.version_labels[k] = label = QtGui.QLabel()
            label.setStyleSheet(dynamic_label_style)
            version_layout.addRow(k+":", label)

        layout.addWidget(trigger_box)
        layout.addWidget(monitor_box)
        layout.addWidget(mode_box)
        layout.addWidget(copy_box)
        layout.addWidget(version_box)

    @pyqtSlot(int)
    def _coincidence_time_changed(self, value):
        self.device.set_coincidence_time(value)

    @pyqtSlot(int)
    def _mult_lo_changed(self, value):
        self.device.set_multiplicity_low(value)

    @pyqtSlot(int)
    def _mult_hi_changed(self, value):
        self.device.set_multiplicity_high(value)

    @pyqtSlot()
    def _copy_panel2rc(self):
        cmd = self.device.get_copy_panel2rc_command()
        self.copy_panel2rc_progress.setMaximum(len(cmd))
        self.copy_panel2rc_progress.setValue(0)
        cmd.progress_changed[int].connect(self.copy_panel2rc_progress.setValue)

        def on_command_stopped():
            cmd.progress_changed[int].disconnect(self.copy_panel2rc_progress.setValue)
            cmd.stopped.disconnect()
            self.copy_panel2rc_stack.setCurrentIndex(0)

        cmd.stopped.connect(on_command_stopped)
        self.copy_panel2rc_stack.setCurrentIndex(1)
        cmd.start()

    @pyqtSlot()
    def _copy_rc2panel(self):
        self.device.perform_copy_function(CopyFunction.rc2panel)

    @pyqtSlot()
    def _copy_common2single(self):
        cmd = self.device.get_copy_common2single_command()
        self.copy_common2single_progress.setMaximum(len(cmd))
        self.copy_common2single_progress.setValue(0)
        cmd.progress_changed[int].connect(self.copy_common2single_progress.setValue)

        def on_command_stopped():
            cmd.progress_changed[int].disconnect(self.copy_common2single_progress.setValue)
            cmd.stopped.disconnect()
            self.stack_copy_common2single.setCurrentIndex(0)

        cmd.stopped.connect(on_command_stopped)
        self.stack_copy_common2single.setCurrentIndex(1)
        cmd.start()

    @pyqtSlot(int)
    def _monitor_channel_selected(self, idx):
        self.device.set_monitor_channel(idx)

    @pyqtSlot(bool)
    def _rb_mode_single_toggled(self, on_off):
        self.device.set_single_channel_mode(on_off)

    def _on_device_coincidence_time_changed(self, value):
        with util.block_signals(self.spin_coincidence_time):
            self.spin_coincidence_time.setValue(value)
        self.label_coincidence_time.setText(
                "%.1f ns" % self.device.get_parameter_by_name('coincidence_time', 'nanoseconds'))

    def _on_device_multiplicity_low_changed(self, value):
        with util.block_signals(self.spin_multiplicity_low):
            self.spin_multiplicity_low.setValue(value)

    def _on_device_multiplicity_high_changed(self, value):
        with util.block_signals(self.spin_multiplicity_high):
            self.spin_multiplicity_high.setValue(value)

    def _on_device_monitor_channel_changed(self, value):
        with util.block_signals(self.combo_monitor):
            self.combo_monitor.setCurrentIndex(value)

    def _on_device_single_channel_mode_changed(self, value):
        rb = self.rb_mode_single if value else self.rb_mode_common
        with util.block_signals(rb):
            rb.setChecked(True)

    def _on_device_parameter_changed(self, bp):
        self.log.debug("parameter_changed: %s", bp)
        def update_version_label(label, value):
            text = "%d.%d" % (version_to_major_minor(value))
            label.setText(text)

        if bp.name == 'hardware_version' and self.device.has_hardware_version():
            update_version_label(self.version_labels['Hardware'], bp.value)
        elif bp.name == 'fpga_version' and self.device.has_fgpa_version():
            update_version_label(self.version_labels['FPGA'], bp.value)
        elif bp.name == 'cpu_software_version' and self.device.has_cpu_software_version():
            update_version_label(self.version_labels['Software'], bp.value)
        elif bp.name == 'version' and self.device.has_version():
            update_version_label(self.version_labels['Software'], bp.value)
            self.version_labels['FPGA'].setText('N/A')
            self.version_labels['Hardware'].setText('N/A')

# FIXME: implement this
class MSCF16SetupWidget(QtGui.QWidget):
    #gain_adjust_changed = pyqtSignal(int, int) # group, value

    def __init__(self, device, context, parent=None):
        super(MSCF16SetupWidget, self).__init__(parent)

        #layout = QtGui.QGridLayout(self)

        #for i in range(MSCF16.num_groups):
        #    group_range = cg_helper.group_channel_range(i)
        #    descr_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1]))
        #    gain_spin   = make_spinbox(limits=MSCF16.gain_adjust_limits)
        #    gain_spin.setValue(device.get_gain_adjust(i))
        #    gain_spin.valueChanged[int].connect(self._on_hw_gain_input_value_changed)

        #    self.hw_gain_inputs.append(gain_spin)

        #    layout.addWidget(descr_label, i+offset, 0, 1, 1, Qt.AlignRight)
        #    layout.addWidget(gain_spin,   i+offset, 1)

# ==========  Module ========== 
idc             = 20
device_class    = MSCF16
device_ui_class = MSCF16Widget
profile_dict    = device_profile_mscf16.profile_dict

if __name__ == "__main__":
    import mock
    import signal
    import sys
    import device_profile_mscf16

    QtGui.QApplication.setDesktopSettingsAware(False)
    app = QtGui.QApplication(sys.argv)
    app.setStyle(QtGui.QStyleFactory.create("Plastique"))

    def signal_handler(signum, frame):
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)

    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    context = mock.Mock()
    device  = mock.Mock()
    device.profile = device_profile_mscf16.get_device_profile()
    device.parameter_changed = mock.MagicMock()
    device.get_total_gain  = mock.MagicMock(return_value=2)
    device.get_gain_adjust = mock.MagicMock(return_value=30)

    w = MSCF16Widget(device, context)
    w.show()

    ret = app.exec_()

    print "context:", context.mock_calls
    print "device:", device.mock_calls

    sys.exit(ret)
