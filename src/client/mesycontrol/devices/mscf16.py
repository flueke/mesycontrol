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

from functools import partial
import collections
import itertools

from .. qt import Signal
from .. qt import Qt
from .. qt import QtCore
from .. qt import QtGui
from .. qt import QtWidgets

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

import mesycontrol.devices.mscf16_profile as mscf16_profile

NUM_CHANNELS        = mscf16_profile.NUM_CHANNELS
NUM_GROUPS          = mscf16_profile.NUM_GROUPS
GAIN_FACTOR         = mscf16_profile.GAIN_FACTOR
GAIN_JUMPER_LIMITS_V  = mscf16_profile.GAIN_JUMPER_LIMITS_V
GAIN_JUMPER_LIMITS_C  = mscf16_profile.GAIN_JUMPER_LIMITS_C
AUTO_PZ_ALL         = NUM_CHANNELS + 1
SHAPING_TIMES_US    = mscf16_profile.SHAPING_TIMES_US
CHANNEL_MODE_COMMON     = 0
CHANNEL_MODE_INDIVIDUAL = 1

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
    WINDIS          = 1 << 3
    SUMDIS          = 1 << 6

    def __init__(self, hw_info=None):
        self.info = hw_info

    def is_ln_type(self):
        """True if LN (low noise) version"""
        return self.is_valid() and self.info & HardwareInfo.LN_TYPE

    def is_hw_version_ge_4(self):
        """True if hardware version >= 4"""
        return self.is_valid() and self.info & HardwareInfo.HW_GE_V4

    def is_integrating(self):
        """True if this is a charge integrating MSCF16 (PMT variant)"""
        return self.is_valid() and self.info & HardwareInfo.INTEGRATING

    def has_sumdis(self):
        return self.is_valid() and self.info & HardwareInfo.SUMDIS

    def has_upper_thresholds(self):
        return self.is_valid() and self.info & HardwareInfo.WINDIS

    def __and__(self, other):
        return self.info & other

    def is_valid(self):
        return self.info is not None

class CopyFunction(object):
    panel2rc        = 1
    rc2panel        = 2
    common2single   = 3

Version = collections.namedtuple('Version', 'major minor')

def get_config_parameters(app_device):
    # Start out with the default parameters defined in the profile. Then try to
    # read the version register and remove parameters accordingly. If the
    # hardware_info register is available use that information to keep/remove
    # additional parameters.
    # If no hardware is present the profile default parameters are returned.

    # FIXME: it might be better to return the minimal profile if no version
    # info can be read. At a later point when hardware is connected and version
    # info is available the list of config parameters has to be updated.

    profile = app_device.profile
    params  = profile.get_config_parameters()

    if not app_device.has_hw:
        return future.Future().set_result(params)

    device  = MSCF16(app_device, util.HARDWARE, util.HARDWARE)
    ret     = future.Future()

    def version_done(f):
        try:
            version = f.result()
        except Exception as e:
            device.log.warning("could not read MSCF-16 version: %s", e)
            ret.set_result(params)
            return

        def maybe_remove(min_version, *param_names):
            if version < min_version:
                device.log.info("version %s < %s -> removing %s",
                        version, min_version, param_names)
                for n in param_names:
                    params.remove(profile[n])

        maybe_remove((4, 0), 'blr_threshold', 'blr_enable', 'coincidence_time',
                'shaper_offset', 'threshold_offset')

        maybe_remove((5, 3), 'sumdis_threshold', 'ecl_delay_enable')

        maybe_remove((5, 4), 'tf_int_time')


        if version >= (5, 3):
            def hw_info_done(f):
                try:
                    hw_info = f.result()
                    if not hw_info.has_sumdis():
                        device.log.info("sumdis_threshold not available according to hw_info register")
                        params.remove(profile['sumdis_threshold'])
                except Exception as e:
                    device.log.warning("could not read MSCF-16 hardware info register: %s", e)

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
    gain_jumper_changed     = Signal(int, float) # group, value
    auto_pz_channel_changed = Signal(int)

    def __init__(self, app_device, read_mode, write_mode, parent=None):
        super(MSCF16, self).__init__(app_device, read_mode, write_mode, parent)
        self.log = util.make_logging_source_adapter(__name__, self)

        self._auto_pz_channel = 0

        self._on_hardware_set(app_device, None, self.hw)
        self.extension_changed.connect(self._on_extension_changed)

    # ===== version registers =====
    def get_version(self):
        """Reads the 'version' register and returns a Future whose result is a
        namedtuple of the form (major, minor)."""

        if not self.has_hw:
            return future.Future().set_exception(
                    pb.ParameterUnavailable("hardware not present"))

        ret = future.Future()

        @set_result_on(ret)
        def done(f):
            return decode_version(int(f.result()))

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
            return decode_fun(int(f.result()))

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

    # FIXME: simplify this. DRY! This also does throw if hardware is not present.
    # The version conditions appear twice: once in get_config_parameters() and again here!
    # Also no user info string can be generated easily, e.g. "Requires version >= 5.3".
    def has_ecl_enable(self):
        ret = future.Future()

        @future.set_result_on(ret)
        def done(f):
            return f.result() >= (5, 3)
        self.get_version().add_done_callback(done)
        return ret

    def has_tf_int_time(self):
        ret = future.Future()

        @future.set_result_on(ret)
        def done(f):
            return f.result() >= (5, 4)
        self.get_version().add_done_callback(done)
        return ret

    def is_charge_integrating(self):
        ret = future.Future()

        @future.set_result_on(ret)
        def hw_info_done(f):
            try:
                return f.result().is_integrating()
            except Exception:
                return self.get_extension('input_type') == 'C'

        self.get_hardware_info().add_done_callback(hw_info_done)

        return ret

    def has_sumdis_threshold(self):
        ret = future.Future()

        @future.set_result_on(ret)
        def hw_info_done(f):
            try:
                return f.result().has_sumdis()
            except Exception:
                return False

        self.get_hardware_info().add_done_callback(hw_info_done)

        return ret

    # ===== gain =====
    # FIXME: update gain labels on hw_info availablity change
    def get_total_gain(self, group):
        ret = future.Future()

        f_gain_group  = self.get_parameter('gain_group%d' % group)
        f_integrating = self.is_charge_integrating()

        @future.set_result_on(ret)
        def done(_):
            gain   = GAIN_FACTOR ** int(f_gain_group.result())
            jumper = self.get_gain_jumper(group)

            if f_integrating.result():
                # Gain adjustable from 100 pC to 20 nC
                return gain / jumper # FIXME: units
            else:
                return gain * jumper # this is unit-less

        future.all_done(f_gain_group, f_integrating).add_done_callback(done)

        return ret

    def get_gain_jumper(self, group):
        return self.get_extension('gain_jumpers')[group]

    def set_gain_jumper(self, group, jumper_value):
        jumpers = self.get_extension('gain_jumpers')

        if jumpers[group] != jumper_value:
            jumpers[group] = jumper_value
            self.set_extension('gain_jumpers', jumpers)

    def apply_common_gain(self):
        return self._apply_common_to_single(
                'gain_common', 'gain_group%d', NUM_GROUPS)

    # ===== shaping time =====
    def get_effective_shaping_time(self, group):
        ret = future.Future()

        @set_result_on(ret)
        def done(f):
            return SHAPING_TIMES_US[self.get_extension('shaping_time')][int(f.result())]

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

    # ===== upper threshold =====
    def apply_upper_common_threshold(self):
        return self._apply_common_to_single(
                'upper_threshold_common', 'upper_threshold_channel%d', NUM_CHANNELS)

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
                futures.append(self.set_parameter(single_param_name_fmt % i, int(f.result())))
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
            # 0 < auto_pz <= NUM_CHANNELS means auto pz is running for that channel
            # self._auto_pz_channel is the last channel that auto pz was running for
            if self._auto_pz_channel is not None and 0 < self._auto_pz_channel <= NUM_CHANNELS:
                self.read_hw_parameter('pz_value_channel%d' % (self._auto_pz_channel-1))

            self._auto_pz_channel = value
            self.auto_pz_channel_changed.emit(value)

    def _on_extension_changed(self, name, value):
        if name == 'gain_jumpers':
            for g, v in enumerate(value):
                self.gain_jumper_changed.emit(g, v)

    def ensure_individual_channel_mode(self):
        """If any of cfg and hw are in common mode change them to individual mode"""
        ret = future.Future()

        def done(f_list):
            try:
                do_set = any(int(f.result()) == CHANNEL_MODE_COMMON for f in f_list.result())

                if do_set:
                    self.log.warning("%s: Detected common channel mode. Setting individual mode.",
                            self.get_display_string())

                    @future.set_result_on(ret)
                    def set_done(f_set):
                        return bool(f_set.result())

                    # This takes the write mode into account. No extra checks need to be done.
                    self.set_parameter('single_channel_mode', CHANNEL_MODE_INDIVIDUAL
                            ).add_done_callback(set_done)
                else:
                    ret.set_result(True)
            except Exception as e:
                self.log.warning("%s: %s", self.get_display_string(), str(e))
                ret.set_exception(e)

        f_list = list()

        if self.write_mode & util.CONFIG and self.has_cfg:
            f_list.append(self.get_cfg_parameter('single_channel_mode'))

        if self.write_mode & util.HARDWARE and self.has_hw:
            f_list.append(self.get_hw_parameter('single_channel_mode'))

        future.all_done(*f_list).add_done_callback(done)

        return ret

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

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(*(4 for i in range(4)))
        layout.setSpacing(4)

        for page in self.pages:
            vbox = QtWidgets.QVBoxLayout()
            vbox.addWidget(page)
            vbox.addStretch(1)
            layout.addItem(vbox)

        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.tab_widget.addTab(widget, device.profile.name)

        self.settings_widget = SettingsWidget(device)
        self.tab_widget.addTab(self.settings_widget, "Settings")

        self.hardware_connected_changed.connect(self._on_hardware_connected_changed)

    def get_parameter_bindings(self):
        return itertools.chain(*(p.bindings for p in self.pages))

    def clear_parameter_bindings(self):
        for p in self.pages:
            p.bindings = list()

    def _on_hardware_connected_changed(self, connected):
        for page in self.pages:
            if hasattr(page, 'handle_hardware_connected_changed'):
                page.handle_hardware_connected_changed(connected)

    def showEvent(self, event):
        if not event.spontaneous():
            self.device.ensure_individual_channel_mode()

        super(MSCF16Widget, self).showEvent(event)

class GainPage(QtWidgets.QGroupBox):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(GainPage, self).__init__("Gain", parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self.device = device

        device.gain_jumper_changed.connect(self._on_device_gain_jumper_changed)
        device.extension_changed.connect(self._on_device_extension_changed)

        self.gain_inputs    = list()
        self.gain_labels    = list()
        self.bindings       = list()

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(QtWidgets.QLabel("Common"), 0, 0, 1, 1, Qt.AlignRight)

        self.gain_common = util.DelayedSpinBox()

        b = pb.factory.make_binding(
                device=device,
                profile=device.profile['gain_common'],
                display_mode=display_mode,
                write_mode=write_mode,
                target=self.gain_common)

        self.bindings.append(b)

        common_layout, self.apply_common_gain_button = util.make_apply_common_button_layout(
                self.gain_common, "Apply to groups", self._apply_common_gain)
        layout.addLayout(common_layout, 0, 1)

        layout.addWidget(make_title_label("Group"),   1, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("RC Gain"), 1, 1, 1, 1, Qt.AlignCenter)
        layout.addWidget(make_title_label("Total"),   1, 2, 1, 1, Qt.AlignCenter)

        offset = layout.rowCount()

        for i in range(NUM_GROUPS):
            group_range = cg_helper.group_channel_range(i)
            descr_label = QtWidgets.QLabel("%d-%d" % (group_range[0], group_range[-1]))
            gain_spin   = util.DelayedSpinBox()
            gain_label  = QtWidgets.QLabel("N/A")
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

    def handle_hardware_connected_changed(self, connected):
        if self.device.read_mode & util.HARDWARE:
            self.apply_common_gain_button.setEnabled(connected)

    @future_progress_dialog()
    def _apply_common_gain(self):
        return self.device.apply_common_gain()

    def _on_device_gain_jumper_changed(self, group, value):
        self._update_gain_label(group)

    def _on_device_extension_changed(self, name, value):
        if name == 'input_type':
            for i in range(NUM_GROUPS):
                self._update_gain_label(i)

    def _update_gain_label_cb(self, f, group):
        self._update_gain_label(group)

    def _update_gain_label(self, group):
        f_gain        = self.device.get_total_gain(group)
        f_integrating = self.device.is_charge_integrating()

        def done(_):
            try:
                if f_integrating.result():
                    tmpl = "%.2f nC"
                else:
                    tmpl = "%.2f"

                self.gain_labels[group].setText(tmpl % f_gain.result())
                self.gain_labels[group].setToolTip(str())
            except Exception as e:
                self.gain_labels[group].setText("N/A")
                self.gain_labels[group].setToolTip(str(e))

        future.all_done(f_gain, f_integrating).add_done_callback(done)

class AutoPZSpin(QtWidgets.QStackedWidget):
    def __init__(self, parent=None):
        super(AutoPZSpin, self).__init__(parent)

        self.spin     = util.DelayedSpinBox()
        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)
        # Ignore the size hint of the progressbar so that only the size of the
        # spinbox is taken into account when calculating the final widget size.
        self.progress.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)

        self.addWidget(self.spin)
        self.addWidget(self.progress)

    def showSpin(self):
        self.setCurrentIndex(0)

    def showProgress(self):
        self.setCurrentIndex(1)

class ShapingPage(QtWidgets.QGroupBox):
    auto_pz_button_size = QtCore.QSize(24, 24)

    def __init__(self, device, display_mode, write_mode, parent=None):
        super(ShapingPage, self).__init__("Shaping", parent)
        self.log    = util.make_logging_source_adapter(__name__, self)

        self.device = device
        self.device.auto_pz_channel_changed.connect(self._on_device_auto_pz_channel_changed)
        self.device.hardware_set.connect(self._on_hardware_set)
        self.device.extension_changed.connect(self._on_device_extension_changed)

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

        sht_common_layout, self.sht_common_button = util.make_apply_common_button_layout(
                self.spin_sht_common, "Apply to groups", self._apply_common_sht)

        pz_common_layout, self.pz_common_button  = util.make_apply_common_button_layout(
                self.spin_pz_common, "Apply to channels", self._apply_common_pz)

        self.pb_auto_pz_all  = QtWidgets.QPushButton("A")
        self.pb_auto_pz_all.setToolTip("Start auto PZ for all channels")
        self.pb_auto_pz_all.setStatusTip(self.pb_auto_pz_all.toolTip())
        self.pb_auto_pz_all.setMaximumSize(ShapingPage.auto_pz_button_size)
        self.pb_auto_pz_all.clicked.connect(partial(self.device.set_auto_pz, channel=AUTO_PZ_ALL))

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(QtWidgets.QLabel("Common"),    0, 0, 1, 1, Qt.AlignRight)
        layout.addLayout(sht_common_layout,         0, 1)
        layout.addWidget(QtWidgets.QLabel("Common"),    0, 3, 1, 1, Qt.AlignRight)
        layout.addLayout(pz_common_layout,          0, 4)
        layout.addWidget(self.pb_auto_pz_all,       0, 5)

        layout.addWidget(make_title_label("Group"),         1, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Shaping time"),  1, 1, 1, 2, Qt.AlignLeft)
        layout.addWidget(make_title_label("Chan"),          1, 3, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("PZ"),            1, 4)

        for chan in range(NUM_CHANNELS):
            group = int(chan / NUM_GROUPS)
            group_range = cg_helper.group_channel_range(group)
            row   = layout.rowCount()

            if chan % NUM_GROUPS == 0:
                descr_label = QtWidgets.QLabel("%d-%d" % (group_range[0], group_range[-1]))
                spin_sht    = util.DelayedSpinBox()
                label_sht   = QtWidgets.QLabel("N/A")
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

            label_chan  = QtWidgets.QLabel("%d" % chan)
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

            button_pz   = QtWidgets.QPushButton("A")
            button_pz.setToolTip("Start auto PZ for channel %d" % chan)
            button_pz.setStatusTip(button_pz.toolTip())
            button_pz.setMaximumSize(ShapingPage.auto_pz_button_size)
            button_pz.clicked.connect(partial(self._auto_pz_button_clicked, channel=chan))
            self.pz_buttons.append(button_pz)

            layout.addWidget(label_chan,    row, 3, 1, 1, Qt.AlignRight)
            layout.addWidget(spin_pz,       row, 4)
            layout.addWidget(button_pz,     row, 5)


        layout.addWidget(hline(), layout.rowCount(), 0, 1, 6)

        self.spin_shaper_offset  = util.DelayedSpinBox()
        self.label_shaper_offset = QtWidgets.QLabel()
        self.label_shaper_offset.setStyleSheet(dynamic_label_style)

        self.spin_blr_threshold = util.DelayedSpinBox()
        self.check_blr_enable   = QtWidgets.QCheckBox()

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['shaper_offset'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_shaper_offset
            ).add_update_callback(self._update_shaper_offset_label_cb))

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
        layout.addWidget(QtWidgets.QLabel("Sh. offset"), row, 0)
        layout.addWidget(self.spin_shaper_offset, row, 1)
        layout.addWidget(self.label_shaper_offset, row, 2)

        row += 1
        layout.addWidget(QtWidgets.QLabel("BLR thresh."), row, 0)
        layout.addWidget(self.spin_blr_threshold, row, 1)

        row += 1
        layout.addWidget(QtWidgets.QLabel("BLR enable"), row, 0)
        layout.addWidget(self.check_blr_enable, row, 1)

        self._on_hardware_set(device, None, device.hw)

    def handle_hardware_connected_changed(self, connected):
        if self.device.read_mode & util.HARDWARE:
            self.sht_common_button.setEnabled(connected)
            self.pz_common_button.setEnabled(connected)

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
                label.setText(text)
            except Exception:
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
            auto_pz = int(f.result())
            # Turn auto pz off if the button of the active channel was clicked.
            # Otherwise turn it on for that channel.
            self.device.set_auto_pz(0 if auto_pz == channel+1 else channel+1)

        self.device.get_auto_pz().add_done_callback(done)

    def _update_shaper_offset_label_cb(self, f):
        value = int(f.result()) - 100
        self.label_shaper_offset.setText("%d" % value)

    def _on_device_extension_changed(self, name, value):
        if name == 'shaping_time':
            for i in range(NUM_GROUPS):
                self._update_sht_label(i)

class TimingPage(QtWidgets.QGroupBox):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(TimingPage, self).__init__("Timing", parent)
        self.device           = device

        self.threshold_inputs = list()
        self.threshold_labels = list()
        self.upper_threshold_inputs = list()
        self.upper_threshold_labels = list()
        self.bindings         = list()
        self.log    = util.make_logging_source_adapter(__name__, self)

        # lower thresholds
        #self.threshold_common = make_spinbox(limits=device.profile['threshold_common'].range.to_tuple())
        self.threshold_common = util.DelayedSpinBox()

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['threshold_common'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.threshold_common))

        threshold_common_layout, self.threshold_common_button = util.make_apply_common_button_layout(
                self.threshold_common, "Apply to channels", self._apply_common_threshold)

        # upper thresholds
        #self.upper_threshold_common = make_spinbox(limits=device.profile['upper_threshold_common'].range.to_tuple())
        self.upper_threshold_common = util.DelayedSpinBox()

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['upper_threshold_common'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.upper_threshold_common)
            .add_update_callback(self._on_upper_threshold_value_updated, spin=self.upper_threshold_common)
            )

        upper_threshold_common_layout, self.upper_threshold_common_button = util.make_apply_common_button_layout(
                self.upper_threshold_common, "Apply to channels", self._apply_upper_common_threshold)

        # populate the grid layout: left side is for the lower, right side for the upper thresholds
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        layout.addWidget(QtWidgets.QLabel("Common"), 0, 0, 1, 1, Qt.AlignRight)
        layout.addLayout(threshold_common_layout, 0, 1)

        layout.addWidget(QtWidgets.QLabel("Common"), 0, 3, 1, 1, Qt.AlignRight)
        layout.addLayout(upper_threshold_common_layout, 0, 4)

        layout.addWidget(make_title_label("Chan"),   1, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Lower Threshold"), 1, 1)

        layout.addWidget(make_title_label("Chan"),   1, 3, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Upper Threshold"), 1, 4)

        info_dicts = (dict(prefix='', coloff=0), dict(prefix='upper_', coloff=3))

        for info in info_dicts:
            is_upper = True if info['prefix'] == 'upper_' else False
            coffset = info['coloff']

            for chan in range(NUM_CHANNELS):
                offset  = 2
                descr_label     = QtWidgets.QLabel("%d" % chan)
                spin_threshold  = util.DelayedSpinBox()
                label_threshold = QtWidgets.QLabel()
                label_threshold.setStyleSheet(dynamic_label_style)

                layout.addWidget(descr_label,       chan+offset, 0+coffset, 1, 1, Qt.AlignRight)
                layout.addWidget(spin_threshold,    chan+offset, 1+coffset)
                layout.addWidget(label_threshold,   chan+offset, 2+coffset)

                if not is_upper:
                    self.threshold_inputs.append(spin_threshold)
                    self.threshold_labels.append(label_threshold)
                else:
                    self.upper_threshold_inputs.append(spin_threshold)
                    self.upper_threshold_labels.append(label_threshold)

                b = pb.factory.make_binding(
                    device=device,
                    profile=device.profile['%sthreshold_channel%d' % (info['prefix'], chan)],
                    display_mode=display_mode,
                    write_mode=write_mode,
                    target=spin_threshold)

                if is_upper:
                    b.add_update_callback(self._on_upper_threshold_value_updated, spin=spin_threshold)

                self.bindings.append(b)

                self.bindings.append(pb.factory.make_binding(
                    device=device,
                    profile=device.profile['%sthreshold_channel%d' % (info['prefix'], chan)],
                    display_mode=display_mode,
                    write_mode=write_mode,
                    target=label_threshold,
                    unit_name='percent'))

        layout.addWidget(hline(), layout.rowCount(), 0, 1, 6)

        self.spin_threshold_offset = util.DelayedSpinBox()
        self.label_threshold_offset = QtWidgets.QLabel()
        self.label_threshold_offset.setStyleSheet(dynamic_label_style)

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['threshold_offset'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_threshold_offset
            ).add_update_callback(self._threshold_offset_cb))

        self.check_ecl_delay = QtWidgets.QCheckBox()

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['ecl_delay_enable'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.check_ecl_delay
            ).add_update_callback(self._ecl_delay_enable_cb))

        self.spin_tf_int_time = util.DelayedSpinBox()

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['tf_int_time'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_tf_int_time
            ).add_update_callback(self._tf_int_time_cb))

        row = layout.rowCount()
        layout.addWidget(QtWidgets.QLabel("Thr. offset"),   row, 0)
        layout.addWidget(self.spin_threshold_offset,    row, 1)
        layout.addWidget(self.label_threshold_offset,   row, 2)

        row += 1
        layout.addWidget(QtWidgets.QLabel("ECL delay"),     row, 0)
        layout.addWidget(self.check_ecl_delay,          row, 1)

        row += 1
        layout.addWidget(QtWidgets.QLabel("TF int. time"),  row, 0)
        layout.addWidget(self.spin_tf_int_time,         row, 1)

        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['hardware_info'],
            display_mode=util.HARDWARE,
            fixed_modes=True,
            ).add_update_callback(
                self._hardware_info_cb))

    @future_progress_dialog()
    def _apply_common_threshold(self):
        return self.device.apply_common_threshold()

    @future_progress_dialog()
    def _apply_upper_common_threshold(self):
        return self.device.apply_upper_common_threshold()

    def _ecl_delay_enable_cb(self, param_future):
        def done(f):
            try:
                self.check_ecl_delay.setEnabled(f.result())
                if not f.result():
                    self.check_ecl_delay.setToolTip("N/A")
            except Exception:
                pass

        self.device.has_ecl_enable().add_done_callback(done)

    def _tf_int_time_cb(self, param_future):
        def done(f):
            try:
                self.spin_tf_int_time.setEnabled(f.result())
                if not f.result():
                    self.spin_tf_int_time.setToolTip("N/A")
            except Exception:
                pass

        self.device.has_tf_int_time().add_done_callback(done)

    def _threshold_offset_cb(self, f):
        value = int(f.result()) - 100
        self.label_threshold_offset.setText("%d" % value)

    def _hardware_info_cb(self, read_mem_future):
        def done(getter_future):
            try:
                hw_info = getter_future.result()
            except Exception:
                hw_info = HardwareInfo()

            self.device.hw_info = hw_info

            en = hw_info.has_upper_thresholds()
            self.log.debug("_hardware_info_cb invoked, has_upper_thresholds=%d", en)
            self.upper_threshold_common.setEnabled(en)
            self.upper_threshold_common_button.setEnabled(en)
            for widget in self.upper_threshold_inputs:
                widget.setEnabled(en)

        self.device.get_hardware_info().add_done_callback(done)

    def _on_upper_threshold_value_updated(self, f, spin):
        if getattr(self.device, 'hw_info'):
            spin.setEnabled(self.device.hw_info.has_upper_thresholds())

    def handle_hardware_connected_changed(self, connected):
        if self.device.read_mode & util.HARDWARE:
            self.threshold_common_button.setEnabled(connected)
            self.upper_threshold_common_button.setEnabled(connected)

class ChannelModeBinding(pb.AbstractParameterBinding):
    def __init__(self, **kwargs):
        super(ChannelModeBinding, self).__init__(**kwargs)
        self.target[0].toggled.connect(self._mode_single_toggled)
        self.target[1].toggled.connect(self._mode_common_toggled)

    def _update(self, rf):
        try:
            rb = self.target[0] if int(rf.result()) else self.target[1]

            with util.block_signals(rb):
                rb.setChecked(True)
        except Exception:
            pass

        for rb in self.target:
            rb.setToolTip(self._get_tooltip(rf))
            rb.setStatusTip(rb.toolTip())

    def _mode_single_toggled(self, checked):
        if checked:
            self._write_value(1)

    def _mode_common_toggled(self, checked):
        if checked:
            self._write_value(0)

class HardwareInfoWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(HardwareInfoWidget, self).__init__(parent)
        self.setStyleSheet('QWidget { background-color: lightgrey; }')

        self.checkboxes = {
                HardwareInfo.LN_TYPE:       ReadOnlyCheckBox("LN type", toolTip="Low Noise Type"),
                HardwareInfo.INTEGRATING:   ReadOnlyCheckBox("Integrating", toolTip="Charge integrating"),
                HardwareInfo.HW_GE_V4:      ReadOnlyCheckBox("HW >= 4", toolTip="Hardware version >= 4"),
                HardwareInfo.SUMDIS:        ReadOnlyCheckBox("SumDis", toolTip="Sum Discriminator"),
                HardwareInfo.WINDIS:        ReadOnlyCheckBox("WinDis", toolTip="Window Discriminator"),
                }

        for cb in self.checkboxes.values():
            cb.setStatusTip(cb.toolTip())

        self.checkbox_tooltips = dict(
                (bit, cb.toolTip()) for bit, cb in self.checkboxes.items())

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.checkboxes[HardwareInfo.HW_GE_V4], 0, 0)
        layout.addWidget(self.checkboxes[HardwareInfo.LN_TYPE], 0, 1)
        layout.addWidget(self.checkboxes[HardwareInfo.INTEGRATING], 1, 0)
        layout.addWidget(self.checkboxes[HardwareInfo.SUMDIS], 1, 1)
        layout.addWidget(self.checkboxes[HardwareInfo.WINDIS], 2, 0)

    def set_hardware_info(self, hw_info):
        for bit, checkbox in self.checkboxes.items():
            checkbox.setChecked(hw_info.is_valid() and hw_info & bit)

            checkbox.setToolTip(self.checkbox_tooltips[bit] if hw_info.is_valid()
                    else "Hardware Info register not supported. Requires version >= 5.3")

class MiscPage(QtWidgets.QWidget):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(MiscPage, self).__init__(parent)
        self.log    = util.make_logging_source_adapter(__name__, self)
        self.device = device
        self.bindings = list()

        self.device.hardware_set.connect(self._on_hardware_set)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Coincidence/Trigger
        trigger_box = QtWidgets.QGroupBox("Coincidence/Trigger")
        trigger_layout = QtWidgets.QGridLayout(trigger_box)
        trigger_layout.setContentsMargins(2, 2, 2, 2)

        self.spin_coincidence_time = util.DelayedSpinBox()
        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['coincidence_time'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_coincidence_time))

        self.label_coincidence_time = QtWidgets.QLabel()
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
        trigger_layout.addWidget(QtWidgets.QLabel("Coinc. time"), row, 0)
        trigger_layout.addWidget(self.spin_coincidence_time,  row, 1)
        trigger_layout.addWidget(self.label_coincidence_time, row, 2)

        row += 1
        trigger_layout.addWidget(QtWidgets.QLabel("Mult. low"),   row, 0)
        trigger_layout.addWidget(self.spin_multiplicity_low, row, 1)

        row += 1
        trigger_layout.addWidget(QtWidgets.QLabel("Mult. high"),   row, 0)
        trigger_layout.addWidget(self.spin_multiplicity_high, row, 1)

        # Monitor
        monitor_box = QtWidgets.QGroupBox("Monitor Channel")
        monitor_layout = QtWidgets.QGridLayout(monitor_box)
        monitor_layout.setContentsMargins(2, 2, 2, 2)
        self.combo_monitor  = QtWidgets.QComboBox()
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
        self.rb_mode_single = QtWidgets.QRadioButton("Individual")
        self.rb_mode_common = QtWidgets.QRadioButton("Common")
        self.rb_mode_common.setEnabled(False)

        self.bindings.append(ChannelModeBinding(
            device=device,
            profile=device.profile['single_channel_mode'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=(self.rb_mode_single, self.rb_mode_common)))

        mode_box = QtWidgets.QGroupBox("Channel Mode")
        mode_layout = QtWidgets.QGridLayout(mode_box)
        mode_layout.setContentsMargins(2, 2, 2, 2)
        mode_layout.addWidget(self.rb_mode_single, 0, 0)
        mode_layout.addWidget(self.rb_mode_common, 0, 1)

        # Copy Functions
        copy_box = QtWidgets.QGroupBox("Copy")
        copy_layout = QtWidgets.QVBoxLayout(copy_box)
        copy_layout.setContentsMargins(2, 2, 2, 2)

        self.pb_copy_panel2rc           = QtWidgets.QPushButton("Panel -> RC", clicked=self._copy_panel2rc)
        self.copy_panel2rc_progress     = QtWidgets.QProgressBar()
        self.copy_panel2rc_stack        = QtWidgets.QStackedWidget()
        self.copy_panel2rc_stack.addWidget(self.pb_copy_panel2rc)
        self.copy_panel2rc_stack.addWidget(self.copy_panel2rc_progress)

        self.pb_copy_rc2panel               = QtWidgets.QPushButton("RC -> Panel", clicked=self._copy_rc2panel)

        self.pb_copy_common2single          = QtWidgets.QPushButton("Common -> Single", clicked=self._copy_common2single)
        self.copy_common2single_progress    = QtWidgets.QProgressBar()
        self.copy_common2single_stack       = QtWidgets.QStackedWidget()
        self.copy_common2single_stack.addWidget(self.pb_copy_common2single)
        self.copy_common2single_stack.addWidget(self.copy_common2single_progress)

        copy_layout.addWidget(self.copy_panel2rc_stack)
        copy_layout.addWidget(self.pb_copy_rc2panel)
        copy_layout.addWidget(self.copy_common2single_stack)

        # Version display
        version_box = QtWidgets.QGroupBox("Version")
        version_layout = QtWidgets.QFormLayout(version_box)
        version_layout.setContentsMargins(2, 2, 2, 2)

        self.version_labels = dict()

        for k, l in (
                ("version", "Version"),
                ("fpga_version", "FPGA"),
                ("cpu_software_version", "CPU")):

            self.version_labels[k] = label = QtWidgets.QLabel()
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
                self._fpga_version_label_cb,
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

        # More
        self.spin_sumdis_threshold = util.DelayedSpinBox()
        self.bindings.append(pb.factory.make_binding(
            device=device,
            profile=device.profile['sumdis_threshold'],
            display_mode=display_mode,
            write_mode=write_mode,
            target=self.spin_sumdis_threshold
            ).add_update_callback(self._sumdis_threshold_cb))

        more_box = QtWidgets.QGroupBox("More")
        more_layout = QtWidgets.QFormLayout(more_box)
        more_layout.setContentsMargins(2, 2, 2, 2)
        more_layout.addRow("SumDis Threshold", self.spin_sumdis_threshold)

        layout.addWidget(trigger_box)
        layout.addWidget(monitor_box)
        layout.addWidget(mode_box)
        layout.addWidget(copy_box)
        layout.addWidget(version_box)
        layout.addWidget(more_box)

        self._on_hardware_set(device, None, device.hw)

    def _on_hardware_set(self, device, old, new):
        hw_is_ok = (new is not None
                and not new.address_conflict
                and not device.idc_conflict)

        self.pb_copy_panel2rc.setEnabled(hw_is_ok)
        self.pb_copy_rc2panel.setEnabled(hw_is_ok)
        self.pb_copy_common2single.setEnabled(hw_is_ok)

        signals = ['connected', 'disconnected', 'address_conflict_changed']

        for sig in signals:
                if old is not None:
                    try:
                        getattr(old, sig).disconnect(self._hardware_state_changed)
                    except TypeError:
                        pass

                if new is not None:
                    getattr(new, sig).connect(self._hardware_state_changed)

        for binding in self.bindings:
            binding.populate()

    def _hardware_state_changed(self):
        hw = self.device.hw
        en = (hw is not None
                and hw.is_connected()
                and not hw.address_conflict)

        for b in (self.pb_copy_panel2rc, self.pb_copy_rc2panel,
                self.pb_copy_common2single):
            b.setEnabled(en)

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

    def _fpga_version_label_cb(self, read_mem_future, label, getter):
        def done(getter_future):
            try:
                version = getter_future.result();
                label.setText("%x.%02x" % (version.major, version.minor))
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

    def _sumdis_threshold_cb(self, read_sumdis_future):
        def done(f):
            try:
                self.spin_sumdis_threshold.setEnabled(f.result())
                if not f.result():
                    self.spin_sumdis_threshold.setToolTip("N/A")
            except Exception:
                pass

        self.device.has_sumdis_threshold().add_done_callback(done)

class SettingsWidget(QtWidgets.QWidget):
    def __init__(self, device, parent=None):
        super(SettingsWidget, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.ui = util.loadUi(":/ui/mscf16_settings.ui", self)
        self.device = device

        # Gain jumpers
        for idx in range(NUM_GROUPS):
            spin = getattr(self.ui, 'spin_gain_jumpers_group%d' % idx)
            spin.setMinimum(GAIN_JUMPER_LIMITS_V[0])
            spin.setMaximum(GAIN_JUMPER_LIMITS_V[1])
            spin.valueChanged.connect(partial(self._spin_gain_jumpers_value_changed, group=idx))

        # Module name
        self.ui.combo_type.addItems(mscf16_profile.MODULE_NAMES)
        self.ui.combo_type.currentIndexChanged.connect(self._type_index_changed)

        # Shaping times
        for sht in mscf16_profile.SHAPING_TIMES:
            self.ui.combo_shaping_times.addItem("SH%d" % sht, sht)

        self.ui.combo_shaping_times.currentIndexChanged.connect(self._shaping_times_index_changed)

        # Input type
        self.ui.combo_input_type.addItems(mscf16_profile.INPUT_TYPES)
        self.ui.combo_input_type.currentIndexChanged.connect(self._input_type_index_changed)

        # Input connector
        self.ui.combo_input_connector.addItems(mscf16_profile.INPUT_CONNECTORS)
        self.ui.combo_input_connector.currentIndexChanged.connect(self._input_connector_index_changed)

        # Discriminator & CFD delay
        for delay in mscf16_profile.CFD_DELAYS:
            self.ui.combo_discriminator.addItem("CFD-%d" % delay, delay)

        self.ui.combo_discriminator.addItem('LE')
        self.ui.combo_discriminator.currentIndexChanged.connect(self._discriminator_index_changed)

        self.device.extension_changed.connect(self._on_device_extension_changed)
        self.device.parameter_changed.connect(self._on_device_parameter_changed)
        self.device.read_mode_changed.connect(self._on_device_read_mode_changed)
        self._on_device_read_mode_changed(device.read_mode)

    # ===== device changes =====
    def _on_device_extension_changed(self, name, ext_value):
        if name == 'gain_jumpers':
            for idx, value in enumerate(ext_value):
                spin = getattr(self.ui, 'spin_gain_jumpers_group%d' % idx)
                with util.block_signals(spin):
                    spin.setValue(float(value))

        elif name == 'module_name':
            idx = self.ui.combo_type.findText(ext_value)
            with util.block_signals(self.ui.combo_type) as o:
                o.setCurrentIndex(idx)

        elif name == 'shaping_time':
            idx = self.ui.combo_shaping_times.findData(ext_value)
            with util.block_signals(self.ui.combo_shaping_times) as o:
                o.setCurrentIndex(idx)

        elif name == 'input_type':
            idx = self.ui.combo_input_type.findText(ext_value)
            with util.block_signals(self.ui.combo_input_type) as o:
                o.setCurrentIndex(idx)

            self._update_gain_jumper_spins()

        elif name == 'input_connector':
            idx = self.ui.combo_input_connector.findText(ext_value)
            with util.block_signals(self.ui.combo_input_connector) as o:
                o.setCurrentIndex(idx)

        elif name in ('discriminator', 'cfd_delay'):
            discriminator = self.device.get_extension('discriminator')
            cfd_delay     = self.device.get_extension('cfd_delay')

            if discriminator == 'LE':
                idx = self.ui.combo_discriminator.findText('LE')
            else:
                idx = self.ui.combo_discriminator.findData(cfd_delay)

            with util.block_signals(self.ui.combo_discriminator) as o:
                o.setCurrentIndex(idx)

    def _on_device_read_mode_changed(self, read_mode):
        self._update_gain_jumper_spins()
        # Create extension change events to repopulate the GUI
        for k, v in self.device.get_extensions().items():
            self._on_device_extension_changed(k, v)

    def _on_device_parameter_changed(self, address, value):
        if address == self.device.profile['hardware_info'].address:
            self._update_gain_jumper_spins()

    def _update_gain_jumper_spins(self):
        def done(f):
            if f.exception() or not f.result():
                limits      = GAIN_JUMPER_LIMITS_V
                suffix      = str()
                decimals    = 0
                ss          = 1.0
            else:
                limits      = GAIN_JUMPER_LIMITS_C
                suffix      = " nC"
                decimals    = 2
                ss          = 0.01

            for idx in range(NUM_GROUPS):
                spin = getattr(self.ui, 'spin_gain_jumpers_group%d' % idx)
                spin.setMinimum(limits[0])
                spin.setMaximum(limits[1])
                spin.setSuffix(suffix)
                spin.setDecimals(decimals)
                spin.setSingleStep(ss)

        self.device.is_charge_integrating().add_done_callback(done)

    # ===== GUI changes =====
    def _spin_gain_jumpers_value_changed(self, value, group):
        self.device.set_gain_jumper(group, value)

    def _type_index_changed(self, idx):
        self.device.set_extension('module_name',
                self.combo_type.itemText(idx))

    def _shaping_times_index_changed(self, idx):
        value, _ = int(self.combo_shaping_times.itemData(idx))
        self.device.set_extension('shaping_time', value)

    def _input_type_index_changed(self, idx):
        self.device.set_extension('input_type',
                self.ui.combo_input_type.itemText(idx))

    def _input_connector_index_changed(self, idx):
        self.device.set_extension('input_connector',
                self.ui.combo_input_connector.itemText(idx))

    def _discriminator_index_changed(self, idx):
        data_variant = self.ui.combo_discriminator.itemData(idx)

        if not data_variant.isValid():
            discriminator = 'LE'
            # Use a valid cfd delay value despite leading edge discriminator.
            # This way when changing from LE to CFD the delay will be valid.
            cfd_delay = mscf16_profile.CFD_DELAYS[0]
        else:
            discriminator = 'CFD'
            cfd_delay, _ = int(data_variant)

        self.device.set_extension('discriminator', discriminator)
        self.device.set_extension('cfd_delay', cfd_delay)

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

    QtWidgets.QApplication.setDesktopSettingsAware(False)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle(QtWidgets.QStyleFactory.create("Plastique"))

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
    device.get_gain_jumper = mock.MagicMock(return_value=30)

    w = MSCF16Widget(device)
    w.show()

    ret = app.exec_()

    print("device:", device.mock_calls)

    sys.exit(ret)
