#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
import collections
import itertools

from .. qt import pyqtSignal
from .. qt import pyqtSlot
from .. qt import Qt
from .. qt import QtCore
from .. qt import QtGui

from .. future import future_progress_dialog
from .. future import set_exception_on
from .. future import set_result_on
from .. import future
from .. import parameter_binding as pb
from .. import util
from .. specialized_device import DeviceBase
from .. specialized_device import DeviceWidgetBase
from .. util import hline
from .. util import make_spinbox
from .. util import make_title_label
from .. util import ReadOnlyCheckBox

import mscf16_profile

NUM_CHANNELS        = mscf16_profile.NUM_CHANNELS
NUM_GROUPS          = mscf16_profile.NUM_GROUPS
GAIN_FACTOR         = mscf16_profile.GAIN_FACTOR
GAIN_ADJUST_LIMITS  = mscf16_profile.GAIN_ADJUST_LIMITS
AUTO_PZ_ALL         = NUM_CHANNELS + 1

# hardware setting (shaping_time extension) -> list indexed by shaping time register
SHAPING_TIMES_US    = {
        1: [0.125, 0.25, 0.5, 1.0],
        2: [0.25,  0.5,  1.0, 2.0],
        4: [0.5,   1.0,  2.0, 4.0],
        8: [1.0,   2.0,  4.0, 8.0]
        }

cg_helper = util.ChannelGroupHelper(NUM_CHANNELS, NUM_GROUPS)

class ModuleInfo(object):
    """Holds information about an MSCF16 that can't be detected via
    software."""

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

    def __init__(self, hw_info=0):
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

    def __and__(self, other):
        return self.info & other

class CopyFunction(object):
    panel2rc        = 1
    rc2panel        = 2
    common2single   = 3

Version = collections.namedtuple('Version', 'major minor')

def get_config_parameters(app_device):
    profile = app_device.profile
    params  = profile.get_config_parameters()

    if not app_device.has_hw:
        return future.Future().set_result(params)

    device  = MSCF16(app_device, util.HARDWARE, util.HARDWARE)
    ret     = future.Future()

    def version_done(f):
        version = f.result()

        def maybe_remove(min_version, *param_names):
            if version < min_version:
                device.log.debug("version %s < %s -> removing %s",
                        version, min_version, param_names)
                for n in param_names:
                    params.remove(profile[n])

        maybe_remove((4, 0), 'blr_threshold', 'blr_enable', 'coincidence_time',
                'shaper_offset', 'threshold_offset')

        maybe_remove((5, 0), 'ecl_delay_enable', 'tf_int_time')

        maybe_remove((5, 3), 'sumdis_threshold')

        if version >= (5, 3):
            def hw_info_done(f):
                hw_info = f.result()

                if not hw_info.has_sumdis():
                    device.log.debug("sumdis_threshold not available according to hw_info register")
                    params.remove(profile['sumdis_threshold'])
                ret.set_result(params)

            device.get_hardware_info().add_done_callback(hw_info_done)
        else:
            ret.set_result(params)

    device.get_version().add_done_callback(version_done)

    return ret

def decode_version(val):
    return Version(*divmod(int(val), 16))

def decode_fpga_version(val):
    return Version(*divmod(int(val), 256))

def decode_cpu_software_version(val):
    return Version(*divmod(int(val), 256))

def decode_hardware_info(val):
    return HardwareInfo(int(val))

# ==========  Device ========== 
class MSCF16(DeviceBase):
    gain_adjust_changed     = pyqtSignal(int, int) # group, value
    auto_pz_channel_changed = pyqtSignal(int)

    def __init__(self, app_device, read_mode, write_mode, parent=None):
        super(MSCF16, self).__init__(app_device, read_mode, write_mode, parent)
        self.log = util.make_logging_source_adapter(__name__, self)

        self._auto_pz_channel = 0

        self._on_hardware_set(app_device, None, self.hw)

    # ===== version registers =====
    def get_version(self):
        """Reads the 'version' register and returns a Future whose result is a
        namedtuple of the form (major, minor)."""

        if not self.has_hw:
            return future.Future().set_exception(pb.ParameterUnavailable("hardware not present"))

        ret = future.Future()

        @set_result_on(ret)
        def done(f):
            return decode_version(int(f))

        self.get_hw_parameter('version').add_done_callback(done)

        return ret

    def has_detailed_versions(self):
        ret = future.Future()

        @set_result_on(ret)
        def done(f):
            version = f.result()
            return version >= Version(5, 3)

        self.get_version().add_done_callback(done)

        return ret

    def _get_detailed_version_parameter(self, param_name, decode_fun):
        ret = future.Future()

        @set_result_on(ret)
        def get_param_done(f):
            return decode_fun(int(f))

        @set_exception_on(ret)
        def has_versions_done(f):
            if f.result():
                self.get_hw_parameter(param_name).add_done_callback(get_param_done)
            else:
                raise RuntimeError("Register '%s' (%d) not supported. Requires version >= 5.3" %
                        (param_name, self.profile[param_name].address))

        self.has_detailed_versions().add_done_callback(has_versions_done)

        return ret

    def get_fpga_version(self):
        return self._get_detailed_version_parameter(
                'fpga_version', decode_fpga_version)

    def get_cpu_software_version(self):
        return self._get_detailed_version_parameter(
                'cpu_software_version', decode_cpu_software_version)

    def get_hardware_info(self):
        return self._get_detailed_version_parameter(
                'hardware_info', decode_hardware_info)

    # ===== gain =====
    def get_total_gain(self, group):
        # FIXME: calculation depends on mscf type (integrating or not)
        ret = future.Future()

        @set_result_on(ret)
        def done(f):
            return GAIN_FACTOR ** int(f) * self.get_gain_adjust(group)

        self.get_parameter('gain_group%d' % group).add_done_callback(done)

        return ret

    def get_gain_adjust(self, group):
        return self.get_extension('gain_adjusts')[group]

    def set_gain_adjust(self, group, gain_adjust):
        adjusts = self.get_extension('gain_adjusts')

        if adjusts[group] != gain_adjust:
            adjusts[group] = gain_adjust
            self.set_extension('gain_adjusts', adjusts)
            self.gain_adjust_changed.emit(group, gain_adjust)

    def apply_common_gain(self):
        return self._apply_common_to_single(
                'gain_common', 'gain_group%d', NUM_GROUPS)

    # ===== shaping time =====
    def get_effective_shaping_time(self, group):
        ret = future.Future()

        @set_result_on(ret)
        def done(f):
            return SHAPING_TIMES_US[self.get_extension('shaping_time')][int(f)]

        self.get_parameter('shaping_time_group%d' % group).add_done_callback(done)

        return ret

    def apply_common_sht(self):
        return self._apply_common_to_single(
                'shaping_time_common', 'shaping_time_group%d', NUM_GROUPS)

    # ===== pz - pole zero =====
    def apply_common_pz(self):
        return self._apply_common_to_single(
                'pz_value_common', 'pz_value_channel%d', NUM_CHANNELS)

    def set_auto_pz(self, channel):
        return self.set_hw_parameter('auto_pz', channel)

    def get_auto_pz(self):
        return self.get_hw_parameter('auto_pz')

    # ===== threshold =====
    def apply_common_threshold(self):
        return self._apply_common_to_single(
                'threshold_common', 'threshold_channel%d', NUM_CHANNELS)

    # ===== copy function =====
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

    # ===== helpers =====
    def _apply_common_to_single(self, common_param_name, single_param_name_fmt, n_single_params):
        ret = future.Future()

        @set_result_on(ret)
        def all_applied(f):
            return all(g.result() for g in f.result())

        @set_exception_on(ret)
        def apply_to_single(f):
            futures = list()
            for i in range(n_single_params):
                futures.append(self.set_parameter(single_param_name_fmt % i, int(f)))
            f_all = future.all_done(*futures).add_done_callback(all_applied)
            future.progress_forwarder(f_all, ret)

        self.get_parameter(common_param_name).add_done_callback(apply_to_single)

        return ret

    def _on_hardware_set(self, app_device, old, new):
        # Overrides DeviceBase._on_hardware_set which is connected by DeviceBase.
        super(MSCF16, self)._on_hardware_set(app_device, old, new)

        if old is not None:
            old.parameter_changed.disconnect(self._on_hw_parameter_changed)

            try:
                old.remove_polling_subscriber(self)
            except KeyError:
                pass

        if new is not None:
            new.parameter_changed.connect(self._on_hw_parameter_changed)

    def _on_hw_parameter_changed(self, address, value):
        if address == self.profile['auto_pz'].address:
            # Refresh the channels PZ value once auto pz is done.
            # auto_pz = 0 means auto pz is not currently running
            # 0 < auto_pz < NUM_CHANNELS means auto pz is running for that channel
            # self._auto_pz_channel is the last channel that auto pz was running for
            if 0 < self._auto_pz_channel <= NUM_CHANNELS:
                self.read_hw_parameter('pz_value_channel%d' % (self._auto_pz_channel-1))

            self._auto_pz_channel = value
            self.auto_pz_channel_changed.emit(value)

# ==========  GUI ========== 
dynamic_label_style = "QLabel { background-color: lightgrey; }"

class MSCF16Widget(DeviceWidgetBase):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(MSCF16Widget, self).__init__(device, display_mode, write_mode, parent)

        self.gain_page      = GainPage(device, display_mode, write_mode, self)
        self.shaping_page   = ShapingPage(device, display_mode, write_mode, self)
        self.timing_page    = TimingPage(device, display_mode, write_mode, self)
        self.misc_page      = MiscPage(device, display_mode, write_mode, self)

        self.pages = [self.gain_page, self.shaping_page, self.timing_page, self.misc_page]

        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(*(4 for i in range(4)))
        layout.setSpacing(4)

        for page in self.pages:
            vbox = QtGui.QVBoxLayout()
            vbox.addWidget(page)
            vbox.addStretch(1)
            layout.addItem(vbox)

    def get_parameter_bindings(self):
        return itertools.chain(*(p.bindings for p in self.pages))

class GainPage(QtGui.QGroupBox):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(GainPage, self).__init__("Gain", parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self.device = device

        device.gain_adjust_changed.connect(self._on_device_gain_adjust_changed)

        self.gain_inputs    = list()
        self.gain_labels    = list()
        self.hw_gain_inputs = list()
        self.bindings       = list()

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(QtGui.QLabel("Common"), 0, 0, 1, 1, Qt.AlignRight)

        self.gain_common = util.DelayedSpinBox()

        b = pb.factory.make_binding(
                device=device,
                profile=device.profile['gain_common'],
                display_mode=display_mode,
                write_mode=write_mode,
                target=self.gain_common)

        self.bindings.append(b)

        common_layout = util.make_apply_common_button_layout(
                self.gain_common, "Apply to groups", self._apply_common_gain)[0]
        layout.addLayout(common_layout, 0, 1)

        layout.addWidget(make_title_label("Group"),   1, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("RC Gain"), 1, 1, 1, 1, Qt.AlignCenter)
        layout.addWidget(make_title_label("Total"),   1, 2, 1, 1, Qt.AlignCenter)

        offset = layout.rowCount()

        for i in range(NUM_GROUPS):
            group_range = cg_helper.group_channel_range(i)
            descr_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1]))
            gain_spin   = util.DelayedSpinBox()
            gain_label  = QtGui.QLabel("N/A")
            gain_label.setStyleSheet(dynamic_label_style)

            self.gain_inputs.append(gain_spin)
            self.gain_labels.append(gain_label)

            b = pb.factory.make_binding(
                    device=device,
                    profile=device.profile['gain_group%d' % i],
                    display_mode=display_mode,
                    write_mode=write_mode,
                    target=gain_spin)

            self.bindings.append(b)

            b.add_update_callback(self._update_gain_label_cb, group=i)

            layout.addWidget(descr_label, i+offset, 0, 1, 1, Qt.AlignRight)
            layout.addWidget(gain_spin,   i+offset, 1)
            layout.addWidget(gain_label,  i+offset, 2, 1, 1, Qt.AlignCenter)

        layout.addWidget(hline(), layout.rowCount(), 0, 1, 3) # hline separator

        layout.addWidget(make_title_label("Gain Jumpers"), layout.rowCount(), 0, 1, 3, Qt.AlignCenter)

        offset = layout.rowCount()

        for i in range(NUM_GROUPS):
            group_range = cg_helper.group_channel_range(i)
            descr_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1]))
            gain_spin   = make_spinbox(limits=GAIN_ADJUST_LIMITS)
            gain_spin.setValue(device.get_gain_adjust(i))
            gain_spin.valueChanged[int].connect(self._on_hw_gain_input_value_changed)

            self.hw_gain_inputs.append(gain_spin)

            layout.addWidget(descr_label, i+offset, 0, 1, 1, Qt.AlignRight)
            layout.addWidget(gain_spin,   i+offset, 1)

    @future_progress_dialog()
    def _apply_common_gain(self):
        return self.device.apply_common_gain()

    @pyqtSlot(int)
    def _on_hw_gain_input_value_changed(self, value):
        s = self.sender()
        g = self.hw_gain_inputs.index(s)
        self.device.set_gain_adjust(g, value)

    def _on_device_gain_adjust_changed(self, group, value):
        spin = self.hw_gain_inputs[group]
        with util.block_signals(spin):
            spin.setValue(value)
        self._update_gain_label(group)

    def _update_gain_label_cb(self, f, group):
        self._update_gain_label(group)

    def _update_gain_label(self, group):
        def done(f):
            try:
                self.gain_labels[group].setText("%.1f" % f.result())
            except Exception as e:
                self.log.warning("_update_gain_label: %s: %s", type(e), e)
                self.gain_labels[group].setText("N/A")

        self.device.get_total_gain(group).add_done_callback(done)

class AutoPZSpin(QtGui.QStackedWidget):
    def __init__(self, parent=None):
        super(AutoPZSpin, self).__init__(parent)

        self.spin     = util.DelayedSpinBox()
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

    def __init__(self, device, display_mode, write_mode, parent=None):
        super(ShapingPage, self).__init__("Shaping", parent)
        self.log    = util.make_logging_source_adapter(__name__, self)

        self.device = device
        self.device.auto_pz_channel_changed.connect(self._on_device_auto_pz_channel_changed)
        self.device.hardware_set.connect(self._on_hardware_set)

        self.stop_icon  = QtGui.QIcon(':/stop.png')
        self.sht_inputs = list()
        self.sht_labels = list()
        self.pz_inputs  = list()
        self.pz_buttons = list()
        self.pz_stacks  = list()
        self.bindings   = list()

        # Columns: group_num, shaping time input, shaping time display, chan_num, pz input, auto pz button

        self.spin_sht_common = util.DelayedSpinBox()

        b = pb.factory.make_binding(
                device=device,
                profile=device.profile['shaping_time_common'],
                display_mode=display_mode,
                write_mode=write_mode,
                target=self.spin_sht_common)

        self.bindings.append(b)

        self.spin_pz_common = util.DelayedSpinBox()

        b = pb.factory.make_binding(
                device=device,
                profile=device.profile['pz_value_common'],
                display_mode=display_mode,
                write_mode=write_mode,
                target=self.spin_pz_common)

        self.bindings.append(b)

        sht_common_layout = util.make_apply_common_button_layout(
                self.spin_sht_common, "Apply to groups", self._apply_common_sht)[0]

        pz_common_layout  = util.make_apply_common_button_layout(
                self.spin_pz_common, "Apply to channels", self._apply_common_pz)[0]

        self.pb_auto_pz_all  = QtGui.QPushButton("A")
        self.pb_auto_pz_all.setToolTip("Start auto PZ for all channels")
        self.pb_auto_pz_all.setStatusTip(self.pb_auto_pz_all.toolTip())
        self.pb_auto_pz_all.setMaximumSize(ShapingPage.auto_pz_button_size)
        self.pb_auto_pz_all.clicked.connect(partial(self.device.set_auto_pz, channel=AUTO_PZ_ALL))

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

        for chan in range(NUM_CHANNELS):
            group = int(chan / NUM_GROUPS)
            group_range = cg_helper.group_channel_range(group)
            row   = layout.rowCount()

            if chan % NUM_GROUPS == 0:
                descr_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1]))
                spin_sht    = util.DelayedSpinBox()
                label_sht   = QtGui.QLabel("N/A")
                label_sht.setStyleSheet(dynamic_label_style)

                layout.addWidget(descr_label,   row, 0, 1, 1, Qt.AlignRight)
                layout.addWidget(spin_sht,      row, 1)
                layout.addWidget(label_sht,     row, 2)

                self.sht_inputs.append(spin_sht)
                self.sht_labels.append(label_sht)

                b = pb.factory.make_binding(
                        device=device,
                        profile=device.profile['shaping_time_group%d' % group],
                        display_mode=display_mode,
                        write_mode=write_mode,
                        target=spin_sht)

                self.bindings.append(b)

                b.add_update_callback(self._update_sht_label_cb, group=group)

            label_chan  = QtGui.QLabel("%d" % chan)
            spin_pz     = AutoPZSpin()
            self.pz_inputs.append(spin_pz.spin)
            self.pz_stacks.append(spin_pz)

            b = pb.factory.make_binding(
                    device=device,
                    profile=device.profile['pz_value_channel%d' % chan],
                    display_mode=display_mode,
                    write_mode=write_mode,
                    target=spin_pz.spin)

            self.bindings.append(b)

            button_pz   = QtGui.QPushButton("A")
            button_pz.setToolTip("Start auto PZ for channel %d" % chan)
            button_pz.setStatusTip(button_pz.toolTip())
            button_pz.setMaximumSize(ShapingPage.auto_pz_button_size)
            button_pz.clicked.connect(partial(self._auto_pz_button_clicked, channel=chan))
            self.pz_buttons.append(button_pz)

            layout.addWidget(label_chan,    row, 3, 1, 1, Qt.AlignRight)
            layout.addWidget(spin_pz,       row, 4)
            layout.addWidget(button_pz,     row, 5)


        layout.addWidget(hline(), layout.rowCount(), 0, 1, 6)

        self.spin_shaper_offset = make_spinbox(limits=device.profile['shaper_offset'].range.to_tuple())
        self.spin_blr_threshold = make_spinbox(limits=device.profile['blr_threshold'].range.to_tuple())
        self.check_blr_enable   = QtGui.QCheckBox()

        self.spin_shaper_offset = util.DelayedSpinBox()
        self.spin_blr_threshold = util.DelayedSpinBox()
        self.check_blr_enable   = QtGui.QCheckBox()

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['shaper_offset'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_shaper_offset))

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['blr_threshold'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_blr_threshold))

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['blr_enable'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.check_blr_enable))

        row = layout.rowCount()
        layout.addWidget(QtGui.QLabel("Sh. offset"), row, 0)
        layout.addWidget(self.spin_shaper_offset, row, 1)

        row += 1
        layout.addWidget(QtGui.QLabel("BLR thresh."), row, 0)
        layout.addWidget(self.spin_blr_threshold, row, 1)

        row += 1
        layout.addWidget(QtGui.QLabel("BLR enable"), row, 0)
        layout.addWidget(self.check_blr_enable, row, 1)

        self._on_hardware_set(device, None, device.hw)

    def _on_hardware_set(self, device, old, new):
        hw_is_ok = new is not None and new.idc == idc

        self.pb_auto_pz_all.setEnabled(hw_is_ok)

        for b in self.pz_buttons:
            b.setEnabled(hw_is_ok)

    @future_progress_dialog()
    def _apply_common_sht(self):
        return self.device.apply_common_sht()

    @future_progress_dialog()
    def _apply_common_pz(self):
        return self.device.apply_common_pz()

    def _update_sht_label_cb(self, ignored_future, group):
        self._update_sht_label(group)

    def _update_sht_label(self, group):
        def done(f):
            try:
                text  = "%.2f µs" % f.result()
                label = self.sht_labels[group]
                label.setText(QtCore.QString.fromUtf8(text))
            except Exception as e:
                self.log.warning("_update_sht_label: %s: %s", type(e), e)
                self.sht_labels[group].setText("N/A")

        self.device.get_effective_shaping_time(group).add_done_callback(done)

    def _on_device_auto_pz_channel_changed(self, value):
        for i, pz_stack in enumerate(self.pz_stacks):
            try:
                button = self.pz_buttons[i]
            except IndexError:
                continue

            if value == 0 or i != value-1:
                pz_stack.showSpin()
                button.setText("A")
                button.setIcon(QtGui.QIcon())
                button.setToolTip("Start auto PZ for channel %d" % i)
            elif i == value-1:
                pz_stack.showProgress()
                button.setText("")
                button.setIcon(self.stop_icon)
                button.setToolTip("Stop auto PZ")

    def _auto_pz_button_clicked(self, channel):
        def done(f):
            auto_pz = int(f)
            # Turn auto pz off if the button of the active channel was clicked.
            # Otherwise turn it on for that channel.
            self.device.set_auto_pz(0 if auto_pz == channel+1 else channel+1)

        self.device.get_auto_pz().add_done_callback(done)

class TimingPage(QtGui.QGroupBox):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(TimingPage, self).__init__("Timing", parent)
        self.device           = device

        self.threshold_inputs = list()
        self.threshold_labels = list()
        self.bindings         = list()

        self.threshold_common = make_spinbox(limits=device.profile['threshold_common'].range.to_tuple())
        self.threshold_common = util.DelayedSpinBox()

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['threshold_common'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.threshold_common))

        threshold_common_layout = util.make_apply_common_button_layout(
                self.threshold_common, "Apply to channels", self._apply_common_threshold)[0]

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(QtGui.QLabel("Common"), 0, 0, 1, 1, Qt.AlignRight)
        layout.addLayout(threshold_common_layout, 0, 1)

        layout.addWidget(make_title_label("Chan"),   1, 0, 1, 1, Qt.AlignRight)
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
                profile=device.profile['threshold_channel%d' % chan],
                display_mode=display_mode,
                write_mode=write_mode,
                target=spin_threshold))

            self.bindings.append(pb.factory.make_binding(
                device=device,
                profile=device.profile['threshold_channel%d' % chan],
                display_mode=display_mode,
                write_mode=write_mode,
                target=label_threshold,
                unit_name='percent'))


        layout.addWidget(hline(), layout.rowCount(), 0, 1, 3)

        self.spin_threshold_offset = util.DelayedSpinBox()

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['threshold_offset'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_threshold_offset))

        self.check_ecl_delay = QtGui.QCheckBox()

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['ecl_delay_enable'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.check_ecl_delay))

        self.spin_tf_int_time = util.DelayedSpinBox()

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['tf_int_time'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_tf_int_time))

        row = layout.rowCount()
        layout.addWidget(QtGui.QLabel("Thr. offset"),   row, 0)
        layout.addWidget(self.spin_threshold_offset,    row, 1)

        row += 1
        layout.addWidget(QtGui.QLabel("ECL delay"),     row, 0)
        layout.addWidget(self.check_ecl_delay,          row, 1)

        row += 1
        layout.addWidget(QtGui.QLabel("TF int. time"),  row, 0)
        layout.addWidget(self.spin_tf_int_time,         row, 1)

    @future_progress_dialog()
    def _apply_common_threshold(self):
        return self.device.apply_common_threshold()

class ChannelModeBinding(pb.AbstractParameterBinding):
    def __init__(self, **kwargs):
        super(ChannelModeBinding, self).__init__(**kwargs)
        self.target[0].toggled.connect(self._write_value)

    def _update(self, rf):
        try:
            rb = self.target[0] if int(rf) else self.target[1]
            with util.block_signals(rb):
                rb.setChecked(True)
        except Exception:
            pass

        for rb in self.target:
            rb.setToolTip(self._get_tooltip(rf))
            rb.setStatusTip(rb.toolTip())

class HardwareInfoWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(HardwareInfoWidget, self).__init__(parent)
        self.setStyleSheet('QWidget { background-color: lightgrey; }')

        self.checkboxes = {
                HardwareInfo.LN_TYPE:       ReadOnlyCheckBox("LN type", toolTip="Low Noise Type"),
                HardwareInfo.INTEGRATING:   ReadOnlyCheckBox("Integrating", toolTip="Charge integrating"),
                HardwareInfo.HW_GE_V4:      ReadOnlyCheckBox("HW >= 4", toolTip="Hardware version >= 4"),
                HardwareInfo.SUMDIS:        ReadOnlyCheckBox("SumDis", toolTip="Sum Discriminator")
                }

        for cb in self.checkboxes.itervalues():
            cb.setStatusTip(cb.toolTip())

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.checkboxes[HardwareInfo.HW_GE_V4], 0, 0)
        layout.addWidget(self.checkboxes[HardwareInfo.LN_TYPE], 0, 1)
        layout.addWidget(self.checkboxes[HardwareInfo.INTEGRATING], 1, 0)
        layout.addWidget(self.checkboxes[HardwareInfo.SUMDIS], 1, 1)

    def set_hardware_info(self, hw_info):
        for bit, checkbox in self.checkboxes.iteritems():
            checkbox.setChecked(hw_info & bit)

class MiscPage(QtGui.QWidget):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(MiscPage, self).__init__(parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self.device = device
        self.bindings = list()

        self.device.hardware_set.connect(self._on_hardware_set)

        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Coincidence/Trigger
        trigger_box = QtGui.QGroupBox("Coincidence/Trigger")
        trigger_layout = QtGui.QGridLayout(trigger_box)
        trigger_layout.setContentsMargins(2, 2, 2, 2)

        self.spin_coincidence_time = util.DelayedSpinBox()
        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['coincidence_time'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_coincidence_time))

        self.label_coincidence_time = QtGui.QLabel()
        self.label_coincidence_time.setStyleSheet(dynamic_label_style)
        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['coincidence_time'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.label_coincidence_time,
            unit_name='nanoseconds'))

        self.spin_multiplicity_high = util.DelayedSpinBox()
        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['multiplicity_hi'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_multiplicity_high))

        self.spin_multiplicity_low = util.DelayedSpinBox()
        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['multiplicity_lo'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_multiplicity_low))

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
        self.combo_monitor.addItems(["Channel %d" % i for i in range(NUM_CHANNELS)])
        self.combo_monitor.setMaxVisibleItems(NUM_CHANNELS+1)

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['monitor_channel'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.combo_monitor))

        monitor_layout.addWidget(self.combo_monitor, 0, 0)

        # Channel mode
        self.rb_mode_single = QtGui.QRadioButton("Individual")
        self.rb_mode_common = QtGui.QRadioButton("Common")

        self.bindings.append(ChannelModeBinding(
            device=device,
            profile=device.profile['single_channel_mode'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=(self.rb_mode_single, self.rb_mode_common)))

        mode_box = QtGui.QGroupBox("Channel Mode")
        mode_layout = QtGui.QGridLayout(mode_box)
        mode_layout.setContentsMargins(2, 2, 2, 2)
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
        self.copy_common2single_stack       = QtGui.QStackedWidget()
        self.copy_common2single_stack.addWidget(self.pb_copy_common2single)
        self.copy_common2single_stack.addWidget(self.copy_common2single_progress)

        copy_layout.addWidget(self.copy_panel2rc_stack)
        copy_layout.addWidget(self.pb_copy_rc2panel)
        copy_layout.addWidget(self.copy_common2single_stack)

        # Version display
        version_box = QtGui.QGroupBox("Version")
        version_layout = QtGui.QFormLayout(version_box)
        version_layout.setContentsMargins(2, 2, 2, 2)

        self.version_labels = dict()

        for k, l in (
                ("version", "Version"),
                ("fpga_version", "FPGA"),
                ("cpu_software_version", "CPU")):

            self.version_labels[k] = label = QtGui.QLabel()
            label.setStyleSheet(dynamic_label_style)
            version_layout.addRow(l+":", label)

        self.hardware_info_widget = HardwareInfoWidget()
        version_layout.addRow("Hardware Info:", self.hardware_info_widget)

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['version'],
            display_mode=util.HARDWARE,
            fixed_modes=True,
            ).add_update_callback(
                self._version_label_cb,
                label=self.version_labels['version'],
                getter=self.device.get_version))

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['fpga_version'],
            display_mode=util.HARDWARE,
            fixed_modes=True,
            ).add_update_callback(
                self._version_label_cb,
                label=self.version_labels['fpga_version'],
                getter=self.device.get_fpga_version))

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['cpu_software_version'],
            display_mode=util.HARDWARE,
            fixed_modes=True,
            ).add_update_callback(
                self._version_label_cb,
                label=self.version_labels['cpu_software_version'],
                getter=self.device.get_cpu_software_version))

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['hardware_info'],
            display_mode=util.HARDWARE,
            fixed_modes=True,
            ).add_update_callback(
                self._hardware_info_cb))

        layout.addWidget(trigger_box)
        layout.addWidget(monitor_box)
        layout.addWidget(mode_box)
        layout.addWidget(copy_box)
        layout.addWidget(version_box)

        self._on_hardware_set(device, None, device.hw)

    def _on_hardware_set(self, device, old, new):
        hw_is_ok = new is not None and new.idc == idc

        self.pb_copy_panel2rc.setEnabled(hw_is_ok)
        self.pb_copy_rc2panel.setEnabled(hw_is_ok)
        self.pb_copy_common2single.setEnabled(hw_is_ok)

        for binding in self.bindings:
            binding.populate()

    def _copy_panel2rc(self):
        def progress(f):
            self.copy_panel2rc_progress.setValue(f.progress())

        def done(f):
            self.copy_panel2rc_stack.setCurrentIndex(0)

        copy_future = self.device.perform_copy_function(CopyFunction.panel2rc)
        copy_future.add_progress_callback(progress)
        copy_future.add_done_callback(done)

        self.copy_panel2rc_progress.setMaximum(copy_future.progress_max())
        self.copy_panel2rc_progress.setValue(0)
        self.copy_panel2rc_stack.setCurrentIndex(1)

    def _copy_rc2panel(self):
        self.device.perform_copy_function(CopyFunction.rc2panel)

    def _copy_common2single(self):
        def progress(f):
            self.copy_common2single_progress.setValue(f.progress())

        def done(f):
            self.copy_common2single_stack.setCurrentIndex(0)

        copy_future = self.device.perform_copy_function(CopyFunction.common2single)
        copy_future.add_progress_callback(progress)
        copy_future.add_done_callback(done)

        self.copy_common2single_progress.setMaximum(copy_future.progress_max())
        self.copy_common2single_progress.setValue(0)
        self.copy_common2single_stack.setCurrentIndex(1)

    def _version_label_cb(self, read_mem_future, label, getter):
        def done(getter_future):
            try:
                version = getter_future.result()
                label.setText("%d.%d" % (version.major, version.minor))
                label.setToolTip(str())
            except Exception as e:
                label.setText("N/A")
                label.setToolTip(str(e))

            label.setStatusTip(label.toolTip())

        getter().add_done_callback(done)

    def _hardware_info_cb(self, read_mem_future):
        def done(getter_future):
            try:
                hw_info = getter_future.result()
            except Exception:
                hw_info = HardwareInfo()

            self.hardware_info_widget.set_hardware_info(hw_info)

        self.device.get_hardware_info().add_done_callback(done)

# FIXME: implement this
class MSCF16SetupWidget(QtGui.QWidget):
    #gain_adjust_changed = pyqtSignal(int, int) # group, value

    def __init__(self, device, parent=None):
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
profile_dict    = mscf16_profile.profile_dict

if __name__ == "__main__":
    import mock
    import signal
    import sys
    import mscf16_profile

    QtGui.QApplication.setDesktopSettingsAware(False)
    app = QtGui.QApplication(sys.argv)
    app.setStyle(QtGui.QStyleFactory.create("Plastique"))

    def signal_handler(signum, frame):
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)

    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    device  = mock.Mock()
    device.profile = mscf16_profile.get_device_profile()
    device.parameter_changed = mock.MagicMock()
    device.get_total_gain  = mock.MagicMock(return_value=2)
    device.get_gain_adjust = mock.MagicMock(return_value=30)

    w = MSCF16Widget(device)
    w.show()

    ret = app.exec_()

    print "device:", device.mock_calls

    sys.exit(ret)
