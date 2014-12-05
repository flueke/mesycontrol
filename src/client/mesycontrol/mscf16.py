#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtSignal
from qt import pyqtSlot
from qt import Qt
from qt import QtCore
from qt import QtGui
from qt import uic
from functools import partial
import weakref

import app_model
import command
import mrc_command
import util

# TODO for the version 2 widget:
# - gain calculation
# - store gain jumper values in the config; restore on load
# - shaping time calculation
# - threshold calculation
# - version display
# - disable version specific inputs

def get_device_info():
    return (MSCF16.idcs, MSCF16)

def get_widget_info():
    return (MSCF16.idcs, MSCF16Widget2)

class CopyFunction(object):
    panel2rc        = 1
    rc2panel        = 2
    common2single   = 3

def version_to_major_minor(version):
   minor = version % 16;
   major = (version - minor) / 16;

   return (major, minor)

def group_channel_range(group_num):
    """Returns the range of channel indexes in the given channel group.
    group_num is the 0-based index of the channel group.
    """
    return xrange(group_num * MSCF16.num_groups, (group_num+1) * MSCF16.num_groups)

class MSCF16(app_model.Device):
    idcs                = (20, )
    num_channels        = 16        # number of channels
    num_groups          =  4        # number of channel groups
    gain_factor         = 1.22      # gain step factor
    gain_adjust_limits  = (1, 1000) # limits of the hardware gain jumpers

    gain_changed                    = pyqtSignal(object)
    threshold_changed               = pyqtSignal(object)
    pz_value_changed                = pyqtSignal(object)
    shaping_time_changed            = pyqtSignal(object)
    single_channel_mode_changed     = pyqtSignal(bool)
    blr_changed                     = pyqtSignal(bool)
    blr_threshold_changed           = pyqtSignal(int)
    multiplicity_high_changed       = pyqtSignal(int)
    multiplicity_low_changed        = pyqtSignal(int)
    threshold_offset_changed        = pyqtSignal(int)
    shaper_offset_changed           = pyqtSignal(int)
    coincidence_time_changed        = pyqtSignal(int)
    monitor_channel_changed         = pyqtSignal(int)
    auto_pz_channel_changed         = pyqtSignal(int)
    copy_function_changed           = pyqtSignal(int)
    version_changed                 = pyqtSignal(int)
    ecl_delay_enable_changed        = pyqtSignal(bool)
    tf_int_time_changed             = pyqtSignal(int)

    gain_adjust_changed             = pyqtSignal(int, int)  # group, gain adjust

    def __init__(self, device_model=None, device_config=None, device_profile=None, parent=None):
        super(MSCF16, self).__init__(device_model=device_model, device_config=device_config,
                device_profile=device_profile, parent=parent)

        self.log = util.make_logging_source_adapter(__name__, self)
        self._auto_pz_channel = 0
        self._gain_adjusts    = [1 for i in range(MSCF16.num_groups)]
        self.parameter_changed[object].connect(self._on_parameter_changed)

    def propagate_state(self):
        """Propagate the current state using the signals defined in this class."""
        if not self.has_model():
            return

        for param_profile in self.profile.parameters:
            if self.has_parameter(param_profile.address):
                self._on_parameter_changed(self.make_bound_parameter(param_profile.address))

    def _on_parameter_changed(self, bp):
        p = self.profile

        if p['gain_group0'] <= bp.address <= p['gain_common']:
            self.gain_changed.emit(bp)

        elif p['threshold_channel0'] <= bp.address <= p['threshold_common']:
            self.threshold_changed.emit(bp)

        elif p['pz_value_channel0'] <= bp.address <= p['pz_value_common']:
            self.pz_value_changed.emit(bp)

        elif p['shaping_time_group0'] <= bp.address <= p['shaping_time_common']:
            self.shaping_time_changed.emit(bp)

        elif bp.name == 'multiplicity_hi':
            self.multiplicity_high_changed.emit(bp.value)

        elif bp.name == 'multiplicity_lo':
            self.multiplicity_low_changed.emit(bp.value)

        elif bp.name == 'monitor_channel':
            self.monitor_channel_changed.emit(bp.value)

        elif bp.name == 'single_channel_mode':
            self.single_channel_mode_changed.emit(bp.value)

        elif bp.name == 'version':
            self.version_changed.emit(bp.value)

        elif bp.name == 'blr_threshold':
            self.blr_threshold_changed.emit(bp.value)

        elif bp.name == 'blr_enable':
            self.blr_changed.emit(bp.value)

        elif bp.name == 'coincidence_time':
            self.coincidence_time_changed.emit(bp.value)

        elif bp.name == 'threshold_offset':
            self.threshold_offset_changed.emit(bp.value)

        elif bp.name == 'shaper_offset':
            self.shaper_offset_changed.emit(bp.value)

        elif bp.name == 'copy_function':
            self.copy_function_changed.emit(bp.value)

        elif bp.name == 'auto_pz':
            # Refresh the channels PZ value once auto pz is done
            if 0 < self._auto_pz_channel <= MSCF16.num_channels:
                self.log.debug("Refreshing pz value for channel %d" % self._auto_pz_channel)

                param_name = 'pz_value_channel%d' % (self._auto_pz_channel-1)
                read_cmd   = mrc_command.ReadParameter(self, param_name)

                # Update the config with the newly found pz value
                def on_read_command_stopped():
                    if not read_cmd.has_failed() and self.has_config():
                        self.log.debug("Updating config pz value")
                        self.config.set_parameter_value(read_cmd.address, read_cmd.get_result())
                    read_cmd.stopped.disconnect()

                read_cmd.stopped.connect(on_read_command_stopped)
                read_cmd.start()

            self._auto_pz_channel = bp.value
            self.auto_pz_channel_changed.emit(bp.value)

        elif bp.name == 'ecl_delay_enable':
            self.ecl_delay_enable_changed.emit(bool(bp.value))

        elif bp.name == 'tf_int_time':
            self.tf_int_time_changed.emit(bp.value)

    def set_gain(self, group, value, response_handler=None):
        return self.set_parameter('gain_group%d' % group, value, response_handler=response_handler)

    def set_common_gain(self, value, response_handler=None):
        return self.set_parameter('gain_common', value, response_handler=response_handler)

    def set_threshold(self, channel, value, response_handler=None):
        return self.set_parameter('threshold_channel%d' % channel, value,  response_handler=response_handler)

    def set_common_threshold(self, value, response_handler=None):
        return self.set_parameter('threshold_common', value, response_handler=response_handler)

    def set_pz_value(self, channel, value, response_handler=None):
        return self.set_parameter('pz_value_channel%d' % channel, value, response_handler=response_handler)

    def set_common_pz_value(self, value, response_handler=None):
        return self.set_parameter('pz_value_common', value, response_handler=response_handler)

    def set_shaping_time(self, group, value, response_handler=None):
        return self.set_parameter('shaping_time_group%d' % group, value, response_handler=response_handler)

    def set_common_shaping_time(self, value, response_handler=None):
        return self.set_parameter('shaping_time_common', value, response_handler=response_handler)

    def set_single_channel_mode(self, value, response_handler=None):
        return self.set_parameter('single_channel_mode', value, response_handler=response_handler)

    def set_blr(self, value, response_handler=None):
        return self.set_parameter('blr_enable', value, response_handler=response_handler)

    def set_blr_threshold(self, value, response_handler=None):
        return self.set_parameter('blr_threshold', value, response_handler=response_handler)

    def set_multiplicity_high(self, value, response_handler=None):
        return self.set_parameter('multiplicity_hi', value, response_handler=response_handler)

    def set_multiplicity_low(self, value, response_handler=None):
        return self.set_parameter('multiplicity_lo', value, response_handler=response_handler)

    def set_threshold_offset(self, value, response_handler=None):
        return self.set_parameter('threshold_offset', value, response_handler=response_handler)

    def set_shaper_offset(self, value, response_handler=None):
        return self.set_parameter('shaper_offset', value, response_handler=response_handler)

    def set_coincidence_time(self, value, response_handler=None):
        return self.set_parameter('coincidence_time', value, response_handler=response_handler)

    def set_monitor_channel(self, value, response_handler=None):
        return self.set_parameter('monitor_channel', value, response_handler=response_handler)

    def set_auto_pz_channel(self, value, response_handler=None):
        return self.set_parameter('auto_pz', value, response_handler=response_handler)

    def get_auto_pz_channel(self):
        return self['auto_pz']

    def set_ecl_delay_enable(self, on_off, response_handler=None):
        return self.set_parameter('ecl_delay_enable', on_off, response_handler=response_handler)

    def set_tf_int_time(self, value, response_handler=None):
        return self.set_parameter('tf_int_time', value, response_handler=response_handler)

    def perform_copy_function(self, value, response_handler=None):
        return self.set_parameter('copy_function', value, response_handler=response_handler)

    def get_copy_panel2rc_command(self):
        return self._get_copy_command(CopyFunction.panel2rc)

    def get_copy_common2single_command(self):
        return self._get_copy_command(CopyFunction.common2single)

    def _get_copy_command(self, copy_operation):
        ret = command.SequentialCommandGroup()
        ret.add(command.Callable(partial(self.mrc.set_polling_enabled, False)))
        ret.add(mrc_command.SetParameter(self, 'copy_function', copy_operation))

        for param_profile in self.profile.parameters:
            cmd = mrc_command.ReadParameter(self, param_profile.address)
            cmd.stopped.connect(self._on_read_after_copy_command_stopped)
            ret.add(cmd)

        ret.add(command.Callable(partial(self.mrc.set_polling_enabled, self.mrc.polling)))
        return ret

    def _on_read_after_copy_command_stopped(self):
        cmd = self.sender()
        cmd.stopped.disconnect(self._on_read_after_copy_command_stopped)

        if not cmd.has_failed() and self.has_config():
            self.config.set_parameter_value(cmd.address, cmd.get_result())

    def get_gain_adjust(self, group):
        return self._gain_adjusts[group]

    def set_gain_adjust(self, group, value):
        self._gain_adjusts[group] = value
        self.gain_adjust_changed.emit(group, value)

    def get_total_gain(self, group):
        return self['gain_group%d' % group] * self.get_gain_adjust(group) * MSCF16.gain_factor


class ChannelSettingsWidget(QtGui.QWidget):
    threshold_changed       = pyqtSignal(int)
    pz_value_changed        = pyqtSignal(int)
    gain_changed            = pyqtSignal(int)
    shaping_time_changed    = pyqtSignal(int)

    def __init__(self, channel_name, group_name, load_ui_file, parent=None):
        super(ChannelSettingsWidget, self).__init__(parent)

        uic.loadUi(load_ui_file('mesycontrol/ui/mscf16_channel_settings.ui'), self)

        self.gb_channel.setTitle(channel_name)
        self.gb_group.setTitle(group_name)

    @pyqtSlot(int)
    def on_spin_threshold_valueChanged(self, value):
        self.threshold_changed.emit(value)

    @pyqtSlot(int)
    def on_spin_pz_value_valueChanged(self, value):
        self.pz_value_changed.emit(value)

    @pyqtSlot(int)
    def on_spin_gain_valueChanged(self, value):
        self.gain_changed.emit(value)

    @pyqtSlot(int)
    def on_spin_shaping_time_valueChanged(self, value):
        self.shaping_time_changed.emit(value)

    def set_threshold(self, value):
        with util.block_signals(self.spin_threshold):
            self.spin_threshold.setValue(value)

    def set_pz_value(self, value):
        with util.block_signals(self.spin_pz_value):
            self.spin_pz_value.setValue(value)

    def set_gain(self, value):
        with util.block_signals(self.spin_gain):
            self.spin_gain.setValue(value)

    def set_shaping_time(self, value):
        with util.block_signals(self.spin_shaping_time):
            self.spin_shaping_time.setValue(value)

class MSCF16Widget(QtGui.QWidget):
    def __init__(self, device, context, parent=None):
        super(MSCF16Widget, self).__init__(parent)
        self.context = context
        self.device  = device
        self.device.add_default_parameter_subscription(self)

        uic.loadUi(self.context.find_data_file(
            'mesycontrol/ui/mscf16_global_settings.ui'), self)

        self.combo_channel.addItem("Common")
        self.combo_channel.addItems(["Channel %d" % (i+1) for i in range(MSCF16.num_channels)])
        self.combo_channel.setMaxVisibleItems(MSCF16.num_channels+1)

        common_settings = ChannelSettingsWidget("Common", "Common Group", self.context.find_data_file)
        common_settings.threshold_changed.connect(self.on_channel_threshold_changed)
        common_settings.pz_value_changed.connect(self.on_channel_pz_value_changed)
        common_settings.gain_changed.connect(self.on_channel_gain_changed)
        common_settings.shaping_time_changed.connect(self.on_channel_shaping_time_changed)

        self.channel_settings = list()
        self.stacked_channels.addWidget(common_settings)
        self.common_settings = weakref.ref(common_settings)

        for i in range(MSCF16.num_channels):
            group_num  = i / MSCF16.num_groups
            chan_first = group_channel_range(group_num)[0] + 1
            chan_last  = group_channel_range(group_num)[-1] + 1

            channel_settings = ChannelSettingsWidget(
                    "Channel %d" % (i+1),
                    "Group %d (Channels %d-%d)" % (group_num + 1, chan_first, chan_last),
                    self.context.find_data_file)

            channel_settings.threshold_changed.connect(self.on_channel_threshold_changed)
            channel_settings.pz_value_changed.connect(self.on_channel_pz_value_changed)
            channel_settings.gain_changed.connect(self.on_channel_gain_changed)
            channel_settings.shaping_time_changed.connect(self.on_channel_shaping_time_changed)
            self.stacked_channels.addWidget(channel_settings)
            self.channel_settings.append(weakref.ref(channel_settings))

        self.combo_auto_pz.addItem("Stop", 0)
        self.combo_auto_pz.addItem("All", 17)
        for i in range(MSCF16.num_channels):
            self.combo_auto_pz.addItem("Channel %d" % (i+1), i+1)
        self.combo_auto_pz.setMaxVisibleItems(MSCF16.num_channels+2)

        self.auto_pz_progress.hide()

        self.device.gain_changed.connect(self.on_device_gain_changed)
        self.device.threshold_changed.connect(self.on_device_threshold_changed)
        self.device.pz_value_changed.connect(self.on_device_pz_value_changed)
        self.device.shaping_time_changed.connect(self.on_device_shaping_time_changed)
        self.device.single_channel_mode_changed.connect(self.on_device_single_channel_mode_changed)
        self.device.blr_changed.connect(self.on_device_blr_changed)
        self.device.blr_threshold_changed.connect(self.on_device_blr_threshold_changed)
        self.device.multiplicity_high_changed.connect(self.on_device_multiplicity_high_changed)
        self.device.multiplicity_low_changed.connect(self.on_device_multiplicity_low_changed)
        self.device.threshold_offset_changed.connect(self.on_device_threshold_offset_changed)
        self.device.shaper_offset_changed.connect(self.on_device_shaper_offset_changed)
        self.device.coincidence_time_changed.connect(self.on_device_coincidence_time_changed)
        self.device.auto_pz_channel_changed.connect(self.on_device_auto_pz_channel_changed)
        self.device.version_changed.connect(self.on_device_version_changed)

        self.device.propagate_state()


    # ========== Auto connections with internal widgets ==========

    @pyqtSlot(bool)
    def on_rb_single_channel_on_toggled(self, on):
        self.device.set_single_channel_mode(on)

    @pyqtSlot(bool)
    def on_rb_blr_on_toggled(self, on):
        self.device.set_blr(on)
    
    @pyqtSlot(int)
    def on_spin_blr_threshold_valueChanged(self, value):
        self.device.set_blr_threshold(value)

    @pyqtSlot(int)
    def on_spin_multiplicity_high_valueChanged (self, value):
        self.device.set_multiplicity_high(value)

    @pyqtSlot(int)
    def on_spin_multiplicity_low_valueChanged(self, value):
        self.device.set_multiplicity_low(value)

    @pyqtSlot(int)
    def on_spin_threshold_offset_valueChanged(self, value):
        self.device.set_threshold_offset(value)

    @pyqtSlot(int)
    def on_spin_shaper_offset_valueChanged(self, value):
        self.device.set_shaper_offset(value)

    @pyqtSlot(int)
    def on_spin_coincidence_time_valueChanged(self, value):
        self.device.set_coincidence_time(value)

    @pyqtSlot(int)
    def on_combo_auto_pz_activated(self, idx):
        value, ok = self.combo_auto_pz.itemData(idx).toInt()
        self.device.set_auto_pz_channel(value)

    @pyqtSlot()
    def on_pb_copy_panel2rc_clicked(self):
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
    def on_pb_copy_rc2panel_clicked(self):
        self.device.perform_copy_function(CopyFunction.rc2panel)

    @pyqtSlot()
    def on_pb_copy_common2single_clicked(self):
        cmd = self.device.get_copy_common2single_command()
        self.copy_common2single_progress.setMaximum(len(cmd))
        self.copy_common2single_progress.setValue(0)
        cmd.progress_changed[int].connect(self.copy_common2single_progress.setValue)

        def on_command_stopped():
            cmd.progress_changed[int].disconnect(self.copy_common2single_progress.setValue)
            cmd.stopped.disconnect()
            self.copy_common2single_stack.setCurrentIndex(0)

        cmd.stopped.connect(on_command_stopped)
        self.copy_common2single_stack.setCurrentIndex(1)
        cmd.start()

    @pyqtSlot(int)
    def on_stacked_channels_currentChanged(self, idx):
        widget = weakref.ref(self.stacked_channels.currentWidget())
        if widget in self.channel_settings:
            self.device.set_monitor_channel(self.channel_settings.index(widget)+1)
        else:
            self.device.set_monitor_channel(0)

    # ========== Channel settings ==========

    def on_channel_threshold_changed(self, value):
        sender = weakref.ref(self.sender())
        if sender == self.common_settings:
            self.device.set_common_threshold(value)
        else:
            self.device.set_threshold(self.channel_settings.index(sender), value)

    def on_channel_pz_value_changed(self, value):
        sender = weakref.ref(self.sender())
        if sender == self.common_settings:
            self.device.set_common_pz_value(value)
        else:
            self.device.set_pz_value(self.channel_settings.index(sender), value)

    def on_channel_gain_changed(self, value):
        sender = weakref.ref(self.sender())
        if sender == self.common_settings:
            self.device.set_common_gain(value)
        else:
            group = self.channel_settings.index(sender) / MSCF16.num_groups
            self.device.set_gain(group, value)

    def on_channel_shaping_time_changed(self, value):
        sender = weakref.ref(self.sender())
        if sender == self.common_settings:
            self.device.set_common_shaping_time(value)
        else:
            group = self.channel_settings.index(sender) / MSCF16.num_groups
            self.device.set_shaping_time(group, value)

    # ========== Slots receiving device changes and populating the GUI ==========

    def on_device_gain_changed(self, bp):
        if bp.has_index():
            for i in group_channel_range(bp.index):
                self.channel_settings[i]().set_gain(bp.value)
        else:
            self.common_settings().set_gain(bp.value)

    def on_device_threshold_changed(self, bp):
        if bp.has_index():
            self.channel_settings[bp.index]().set_threshold(bp.value)
        else:
            self.common_settings().set_threshold(bp.value)

    def on_device_pz_value_changed(self, bp):
        if bp.has_index():
            self.channel_settings[bp.index]().set_pz_value(bp.value)
        else:
            self.common_settings().set_pz_value(bp.value)

    def on_device_shaping_time_changed(self, bp):
        if bp.has_index():
            for i in group_channel_range(bp.index):
                self.channel_settings[i]().set_shaping_time(bp.value)
            else:
                self.common_settings().set_shaping_time(bp.value)

    def on_device_single_channel_mode_changed(self, on):
        with util.block_signals(self.rb_single_channel_on):
            self.rb_single_channel_on.setChecked(on)

        with util.block_signals(self.rb_single_channel_off):
            self.rb_single_channel_off.setChecked(not on)

    def on_device_blr_changed(self, on):
        with util.block_signals(self.rb_blr_on):
            self.rb_blr_on.setChecked(on)

        with util.block_signals(self.rb_blr_off):
            self.rb_blr_off.setChecked(not on)

    def on_device_blr_threshold_changed(self, value):
        with util.block_signals(self.spin_blr_threshold):
            self.spin_blr_threshold.setValue(value)

    def on_device_multiplicity_high_changed(self, value):
        with util.block_signals(self.spin_multiplicity_high):
            self.spin_multiplicity_high.setValue(value)

    def on_device_multiplicity_low_changed(self, value):
        with util.block_signals(self.spin_multiplicity_low):
            self.spin_multiplicity_low.setValue(value)

    def on_device_threshold_offset_changed(self, value):
        with util.block_signals(self.spin_threshold_offset):
            self.spin_threshold_offset.setValue(value)

    def on_device_shaper_offset_changed(self, value):
        with util.block_signals(self.spin_shaper_offset):
            self.spin_shaper_offset.setValue(value)

    def on_device_coincidence_time_changed(self, value):
        with util.block_signals(self.spin_coincidence_time):
            self.spin_coincidence_time.setValue(value)

    def on_device_auto_pz_channel_changed(self, value):
        self.auto_pz_progress.setVisible(value != 0)
        text = '-' if value == 0 else str(value)
        self.label_current_auto_pz_channel.setText(text)

    def on_device_version_changed(self, value):
        text = "%d.%d" % version_to_major_minor(value)
        self.label_version.setText(text)

def make_title_label(title):
    title_font = QtGui.QFont()
    title_font.setBold(True)
    label = QtGui.QLabel(title)
    label.setFont(title_font)
    label.setAlignment(Qt.AlignCenter)
    return label

def hline(parent=None):
    ret = QtGui.QFrame(parent)
    ret.setFrameShape(QtGui.QFrame.HLine)
    ret.setFrameShadow(QtGui.QFrame.Sunken)
    return ret

def vline(parent=None):
    ret = QtGui.QFrame(parent)
    ret.setFrameShape(QtGui.QFrame.VLine)
    ret.setFrameShadow(QtGui.QFrame.Sunken)
    return ret

def make_spinbox(min_value=None, max_value=None, limits=None, parent=None):
    ret = QtGui.QSpinBox(parent)
    if min_value is not None:
        ret.setMinimum(min_value)
    if max_value is not None:
        ret.setMaximum(max_value)
    if limits is not None:
        ret.setMinimum(limits[0])
        ret.setMaximum(limits[1])
    return ret

class GainPage(QtGui.QGroupBox):
    def __init__(self, device, parent=None):
        super(GainPage, self).__init__("Gain", parent)
        self.device         = device
        device.gain_changed.connect(self._on_device_gain_changed)
        device.gain_adjust_changed.connect(self._on_device_gain_adjust_changed)

        self.gain_inputs    = list()
        self.gain_labels    = list()
        self.hw_gain_inputs = list()

        gain_min_max = device.profile['gain_common'].range.to_tuple()

        layout = QtGui.QGridLayout(self)

        layout.addWidget(QtGui.QLabel("Common"), 0, 0)
        self.gain_common = make_spinbox(limits=gain_min_max)
        self.gain_common.valueChanged[int].connect(self._on_gain_input_value_changed)
        layout.addWidget(self.gain_common, 0, 1)

        layout.addWidget(make_title_label("RC Gain"), 1, 0, 1, 3, Qt.AlignCenter)

        offset = layout.rowCount()

        for i in range(MSCF16.num_groups):
            group_range = group_channel_range(i)
            descr_label = QtGui.QLabel("Ch. %d-%d" % (group_range[0], group_range[-1]))
            gain_spin   = make_spinbox(limits=gain_min_max)
            gain_label  = QtGui.QLabel("1.0") # XXX

            gain_spin.valueChanged[int].connect(self._on_gain_input_value_changed)

            self.gain_inputs.append(gain_spin)
            self.gain_labels.append(gain_label)

            layout.addWidget(descr_label, i+offset, 0)
            layout.addWidget(gain_spin,   i+offset, 1)
            layout.addWidget(gain_label,  i+offset, 2)

        layout.addWidget(hline(), layout.rowCount(), 0, 1, 3) # hline separator

        layout.addWidget(make_title_label("Gain Jumpers"), layout.rowCount(), 0, 1, 3, Qt.AlignCenter)

        offset = layout.rowCount()

        for i in range(MSCF16.num_groups):
            group_range = group_channel_range(i)
            descr_label = QtGui.QLabel("Ch. %d-%d" % (group_range[0], group_range[-1]))
            gain_spin   = make_spinbox(limits=MSCF16.gain_adjust_limits)
            gain_spin.valueChanged[int].connect(self._on_hw_gain_input_value_changed)

            self.hw_gain_inputs.append(gain_spin)

            layout.addWidget(descr_label, i+offset, 0)
            layout.addWidget(gain_spin,   i+offset, 1)

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

    def _on_device_gain_adjust_changed(self, group, value):
        spin = self.hw_gain_inputs[group]
        with util.block_signals(spin):
            spin.setValue(value)

class AutoPZSpin(QtGui.QStackedWidget):
    def __init__(self, limits=None, parent=None):
        super(AutoPZSpin, self).__init__(parent)

        self.spin = QtGui.QSpinBox()
        if limits is not None:
            self.spin.setMinimum(limits[0])
            self.spin.setMaximum(limits[1])

        self.progress = QtGui.QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)

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

        self.stop_icon  = QtGui.QIcon(context.find_data_file('mesycontrol/ui/process-stop.png'))
        self.sht_inputs = list()
        self.pz_inputs  = list()
        self.pz_buttons = list()
        self.pz_stacks  = list()

        shaping_time_limits = device.profile['shaping_time_common'].range.to_tuple()
        pz_value_limits     = device.profile['pz_value_common'].range.to_tuple()

        # Columns: group_num, shaping time input, shaping time display, chan_num, pz input, auto pz button

        layout = QtGui.QGridLayout(self)

        self.spin_sht_common    = make_spinbox(limits=shaping_time_limits)
        self.spin_sht_common.valueChanged[int].connect(self._on_shaping_time_value_changed)

        self.spin_pz_common     = make_spinbox(limits=pz_value_limits)
        self.spin_pz_common.valueChanged[int].connect(self._on_pz_value_changed)

        self.pb_auto_pz_all  = QtGui.QPushButton("A")
        self.pb_auto_pz_all.setToolTip("Start auto PZ for all channels")
        self.pb_auto_pz_all.setStatusTip(self.pb_auto_pz_all.toolTip())
        self.pb_auto_pz_all.setMaximumSize(ShapingPage.auto_pz_button_size)
        self.pb_auto_pz_all.clicked.connect(self._on_auto_pz_button_clicked)

        layout.addWidget(QtGui.QLabel("Common"),    0, 0)
        layout.addWidget(self.spin_sht_common,      0, 1)
        layout.addWidget(QtGui.QLabel("Common"),    0, 3)
        layout.addWidget(self.spin_pz_common,       0, 4)
        layout.addWidget(self.pb_auto_pz_all,       0, 5)

        layout.addWidget(make_title_label("Sht."),  1, 1)
        layout.addWidget(make_title_label("PZ"),    1, 4)

        for chan in range(MSCF16.num_channels):
            group = int(chan / MSCF16.num_groups)
            group_range = group_channel_range(group)
            row   = layout.rowCount()

            if chan % MSCF16.num_groups == 0:
                descr_label = QtGui.QLabel("Ch. %d-%d" % (group_range[0], group_range[-1]))
                spin_sht    = make_spinbox(limits=shaping_time_limits)
                label_sht   = QtGui.QLabel(QtCore.QString.fromUtf8("42.0 µs")) # XXX

                layout.addWidget(descr_label,   row, 0)
                layout.addWidget(spin_sht,      row, 1)
                layout.addWidget(label_sht,     row, 2)

                self.sht_inputs.append(spin_sht)
                spin_sht.valueChanged[int].connect(self._on_shaping_time_value_changed)

            label_chan  = QtGui.QLabel("Ch. %d" % chan)
            spin_pz     = AutoPZSpin(limits=pz_value_limits)
            spin_pz.spin.valueChanged[int].connect(self._on_pz_value_changed)
            self.pz_inputs.append(spin_pz.spin)
            self.pz_stacks.append(spin_pz)

            button_pz   = QtGui.QPushButton("A")
            button_pz.setMaximumSize(ShapingPage.auto_pz_button_size)
            button_pz.clicked.connect(self._on_auto_pz_button_clicked)
            self.pz_buttons.append(button_pz)

            layout.addWidget(label_chan,    row, 3)
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

    # ===== Device changes =====
    def _on_device_shaping_time_changed(self, bp):
        spin = self.spin_sht_common if not bp.has_index() else self.sht_inputs[bp.index]
        with util.block_signals(spin):
            spin.setValue(bp.value)

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
            elif i == value-1:
                pz_stack.showProgress()
                self.pz_buttons[i].setText("")
                self.pz_buttons[i].setIcon(self.stop_icon)

class TimingPage(QtGui.QGroupBox):
    def __init__(self, device, parent=None):
        super(TimingPage, self).__init__("Timing", parent)
        self.device           = device
        self.device.threshold_changed.connect(self._on_device_threshold_changed)
        self.device.threshold_offset_changed.connect(self._on_device_threshold_offset_changed)
        self.device.ecl_delay_enable_changed.connect(self._on_device_ecl_enable_changed)
        self.device.tf_int_time_changed.connect(self._on_device_tf_int_time_changed)

        self.threshold_common = QtGui.QSpinBox()
        self.threshold_inputs = list()
        self.threshold_labels = list()

        self.threshold_common.valueChanged[int].connect(self._on_threshold_changed)

        layout = QtGui.QGridLayout(self)
        layout.addWidget(QtGui.QLabel("Common"), 0, 0)
        layout.addWidget(self.threshold_common, 0, 1)

        layout.addWidget(make_title_label("Threshold"), 1, 1)

        for chan in range(MSCF16.num_channels):
            offset  = 2
            descr_label     = QtGui.QLabel("Ch. %d" % chan)
            spin_threshold  = QtGui.QSpinBox()
            label_threshold = QtGui.QLabel("?")

            layout.addWidget(descr_label,       chan+offset, 0)
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

    def _on_device_threshold_changed(self, bp):
        spin = self.threshold_common if not bp.has_index() else self.threshold_inputs[bp.index]
        with util.block_signals(spin):
            spin.setValue(bp.value)

    def _on_device_threshold_offset_changed(self, value):
        with util.block_signals(self.spin_threshold_offset):
            self.spin_threshold_offset.setValue(value)

    def _on_device_ecl_enable_changed(self, on_off):
        with util.block_signals(self.check_ecl_delay):
            self.check_ecl_delay.setEnabled(on_off)

    def _on_device_tf_int_time_changed(self, value):
        with util.block_signals(self.spin_tf_int_time):
            self.spin_tf_int_time.setValue(value)

class MiscPage(QtGui.QWidget):
    def __init__(self, device, parent=None):
        super(MiscPage, self).__init__(parent)
        self.device = device
        self.device.coincidence_time_changed.connect(self._on_device_coincidence_time_changed)
        self.device.multiplicity_low_changed.connect(self._on_device_multiplicity_low_changed)
        self.device.multiplicity_high_changed.connect(self._on_device_multiplicity_high_changed)
        self.device.monitor_channel_changed.connect(self._on_device_monitor_channel_changed)

        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(*[0 for i in range(4)])

        # Coincidence/Trigger
        trigger_box = QtGui.QGroupBox("Coincidence/Trigger")
        trigger_layout = QtGui.QGridLayout(trigger_box)

        self.spin_coincidence_time  = make_spinbox(limits=device.profile['coincidence_time'].range.to_tuple())
        self.spin_multiplicity_high = make_spinbox(limits=device.profile['multiplicity_hi'].range.to_tuple())
        self.spin_multiplicity_low  = make_spinbox(limits=device.profile['multiplicity_lo'].range.to_tuple())

        self.spin_coincidence_time.valueChanged[int].connect(self._coincidence_time_changed)
        self.spin_multiplicity_low.valueChanged[int].connect(self._mult_lo_changed)
        self.spin_multiplicity_high.valueChanged[int].connect(self._mult_hi_changed)

        row = 0
        trigger_layout.addWidget(QtGui.QLabel("Coinc. time"), row, 0)
        trigger_layout.addWidget(self.spin_coincidence_time,  row, 1)

        row += 1
        trigger_layout.addWidget(QtGui.QLabel("Mult-low"),   row, 0)
        trigger_layout.addWidget(self.spin_multiplicity_low, row, 1)

        row += 1
        trigger_layout.addWidget(QtGui.QLabel("Mult-high"),   row, 0)
        trigger_layout.addWidget(self.spin_multiplicity_high, row, 1)

        # Monitor
        monitor_box = QtGui.QGroupBox("Monitor Channel")
        monitor_layout = QtGui.QGridLayout(monitor_box)
        self.combo_monitor  = QtGui.QComboBox()
        self.combo_monitor.addItems(["Channel %d" % i for i in range(MSCF16.num_channels)])
        self.combo_monitor.setMaxVisibleItems(MSCF16.num_channels+1)
        self.combo_monitor.currentIndexChanged[int].connect(self._monitor_channel_selected)
        monitor_layout.addWidget(self.combo_monitor, 0, 0)

        # Copy Functions
        copy_box = QtGui.QGroupBox("Copy")
        copy_layout = QtGui.QVBoxLayout(copy_box)

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

        layout.addWidget(trigger_box)
        layout.addWidget(monitor_box)
        layout.addWidget(copy_box)

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

    def _on_device_coincidence_time_changed(self, value):
        with util.block_signals(self.spin_coincidence_time):
            self.spin_coincidence_time.setValue(value)

    def _on_device_multiplicity_low_changed(self, value):
        with util.block_signals(self.spin_multiplicity_low):
            self.spin_multiplicity_low.setValue(value)

    def _on_device_multiplicity_high_changed(self, value):
        with util.block_signals(self.spin_multiplicity_high):
            self.spin_multiplicity_high.setValue(value)

    def _on_device_monitor_channel_changed(self, value):
        with util.block_signals(self.combo_monitor):
            self.combo_monitor.setCurrentIndex(value)

class MSCF16Widget2(QtGui.QWidget):
    def __init__(self, device, context, parent=None):
        super(MSCF16Widget2, self).__init__(parent)
        self.context = context
        self.device  = device
        self.device.add_default_parameter_subscription(self)

        self.gain_page      = GainPage(device, self)
        self.shaping_page   = ShapingPage(device, context, self)
        self.timing_page    = TimingPage(device, self)
        self.misc_page      = MiscPage(device, self)

        pages = [self.gain_page, self.shaping_page, self.timing_page, self.misc_page]

        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        for page in pages:
            vbox = QtGui.QVBoxLayout()
            vbox.addWidget(page)
            vbox.addStretch(1)
            layout.addItem(vbox)

        self.device.propagate_state()

if __name__ == "__main__":
    import mock
    import sys
    import device_profile_mscf16

    QtGui.QApplication.setDesktopSettingsAware(False)
    app = QtGui.QApplication(sys.argv)

    context = mock.Mock()
    device  = mock.Mock()
    device.profile = device_profile_mscf16.get_device_profile()
    device.get_total_gain = mock.MagicMock(return_value=2)

    w = MSCF16Widget2(device, context)
    w.show()

    sys.exit(app.exec_())
