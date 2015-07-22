#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
import collections

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
from .. util import hline
from .. util import make_spinbox
from .. util import make_title_label

import device_profile_mscf16

NUM_CHANNELS        = device_profile_mscf16.NUM_CHANNELS
NUM_GROUPS          = device_profile_mscf16.NUM_GROUPS
GAIN_FACTOR         = device_profile_mscf16.GAIN_FACTOR
GAIN_ADJUST_LIMITS  = device_profile_mscf16.GAIN_ADJUST_LIMITS
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

Version = collections.namedtuple('Version', 'major minor')

def version_to_major_minor(version):
   minor = version % 16;
   major = (version - minor) / 16;

   return Version(major, minor)

def get_config_parameters(app_device):
    # TODO: implement version dependent code here
    return future.Future().set_result(app_device.profile.get_config_parameters())

# ==========  Device ========== 
class MSCF16(DeviceBase):
    gain_adjust_changed = pyqtSignal(int, int) # group, value
    auto_pz_channel_changed = pyqtSignal(int)

    def __init__(self, app_device, read_mode, write_mode, parent=None):
        super(MSCF16, self).__init__(app_device, read_mode, write_mode, parent)
        self.log = util.make_logging_source_adapter(__name__, self)

        self._auto_pz_channel = 0

        self._on_hardware_set(app_device, None, self.hw)

    # ===== version registers =====
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

            for addr in self.profile.get_volatile_addresses():
                new.add_poll_item(self, addr)

    def _on_hw_parameter_changed(self, address, value):
        if address == self.profile['auto_pz'].address:
            # Refresh the channels PZ value once auto pz is done.
            # auto_pz = 0 means auto pz is not currently running
            # 0 < auto_pz < NUM_CHANNELS means auto pz is running for that channel
            # self._auto_pz_channel is the last channel that auto pz was running for
            print "===== _on_hw_parameter_changed: is auto_pz", address, value

            if 0 < self._auto_pz_channel <= NUM_CHANNELS:
                print "=============== refreshing pz value for channel", self._auto_pz_channel
                self.read_hw_parameter('pz_value_channel%d' % (self._auto_pz_channel-1))

            self._auto_pz_channel = value
            self.auto_pz_channel_changed.emit(value)

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

        self.pages = [self.gain_page, self.shaping_page, self.timing_page, self.misc_page]

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

def make_apply_common_button_layout(input_spinbox, tooltip, on_clicked):

    # Wrapper to invoke the clicked handler without the boolean arg that's
    # passed from QPushButton.clicked().
    def _on_clicked(_ignored):
        on_clicked()

    button = QtGui.QPushButton(clicked=_on_clicked)
    button.setIcon(QtGui.QIcon(":/arrow-bottom.png"))
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
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(GainPage, self).__init__("Gain", parent)
        self.device         = device

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

        common_layout = make_apply_common_button_layout(
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

        self.stop_icon  = QtGui.QIcon(':/ui/process-stop.png')
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

        sht_common_layout = make_apply_common_button_layout(
                self.spin_sht_common, "Apply to groups", self._apply_common_sht)[0]

        pz_common_layout  = make_apply_common_button_layout(
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
        print "====== gui: _on_device_auto_pz_channel_changed", value
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

        threshold_common_layout = make_apply_common_button_layout(
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

class MiscPage(QtGui.QWidget):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(MiscPage, self).__init__(parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self.device = device
        self.bindings = list()

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
        self.rb_mode_single = QtGui.QRadioButton("Single")
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

    device  = mock.Mock()
    device.profile = device_profile_mscf16.get_device_profile()
    device.parameter_changed = mock.MagicMock()
    device.get_total_gain  = mock.MagicMock(return_value=2)
    device.get_gain_adjust = mock.MagicMock(return_value=30)

    w = MSCF16Widget(device)
    w.show()

    ret = app.exec_()

    print "device:", device.mock_calls

    sys.exit(ret)
