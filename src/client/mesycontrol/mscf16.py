#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtGui
from PyQt4 import uic
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import pyqtSlot
from functools import partial
import weakref

import application_registry
import app_model
import command
import mrc_command
import util

def get_device_info():
    return (MSCF16.idcs, MSCF16)

def get_widget_info():
    return (MSCF16.idcs, MSCF16Widget)

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
    idcs         = (20, )
    num_channels = 16
    num_groups   =  4

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

    def __init__(self, device_model=None, device_config=None, device_profile=None, parent=None):
        super(MSCF16, self).__init__(device_model=device_model, device_config=device_config,
                device_profile=device_profile, parent=parent)

        self.log = util.make_logging_source_adapter(__name__, self)
        self._auto_pz_channel = 0
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

        if p['gain_group0'] <= bp.profile <= p['gain_common']:
            self.gain_changed.emit(bp)

        elif p['threshold_channel0'] <= bp.profile <= p['threshold_common']:
            self.threshold_changed.emit(bp)

        elif p['pz_value_channel0'] <= bp.profile <= p['pz_value_common']:
            self.pz_value_changed.emit(bp)

        elif p['shaping_time_group0'] <= bp.profile <= p['shaping_time_common']:
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


class ChannelSettingsWidget(QtGui.QWidget):
    threshold_changed       = pyqtSignal(int)
    pz_value_changed        = pyqtSignal(int)
    gain_changed            = pyqtSignal(int)
    shaping_time_changed    = pyqtSignal(int)

    def __init__(self, channel_name, group_name, parent=None):
        super(ChannelSettingsWidget, self).__init__(parent)

        uic.loadUi(application_registry.instance.find_data_file(
            'mesycontrol/ui/mscf16_channel_settings.ui'), self)

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
    def __init__(self, device, parent=None):
        super(MSCF16Widget, self).__init__(parent)
        self.device = device
        self.device.add_default_parameter_subscription(self)

        uic.loadUi(application_registry.instance.find_data_file(
            'mesycontrol/ui/mscf16_global_settings.ui'), self)

        self.combo_channel.addItem("Common")
        self.combo_channel.addItems(["Channel %d" % (i+1) for i in range(MSCF16.num_channels)])
        self.combo_channel.setMaxVisibleItems(MSCF16.num_channels+1)

        common_settings = ChannelSettingsWidget("Common", "Common Group")
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
                    "Group %d (Channels %d-%d)" % (group_num + 1, chan_first, chan_last))

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
