#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtProperty
from qt import pyqtSignal
from qt import pyqtSlot
from qt import Qt
from qt import QtCore
from qt import QtGui
import math
import re

import app_model
import util

from app_model import modifies_extensions
from util import make_title_label, hline, make_spinbox

# MCFD16 - 16 channel CFD
# Hardware dependent tunables:
# * Delay: the RC delay values depend on the delay chip in use. Dividing the
#   chips max delay by the number of taps (5) yields the delay step.
#   => Only the max delay needs to be configured

def get_device_info():
    return (MCFD16.idcs, MCFD16)

def get_widget_info():
    return (MCFD16.idcs, MCFD16Widget)

class Polarity(object):
    negative = 1
    positive = 0

class DiscriminatorMode(object):
    le  = 0
    cfd = 1

def group_channel_range(group_num):
    """Returns the range of channel indexes in the given channel group.
    group_num is the 0-based index of the channel group.
    """
    channels_per_group = MCFD16.num_channels / MCFD16.num_groups
    return xrange(group_num * channels_per_group, (group_num+1) * channels_per_group)

def channel_to_group(channel_idx):
    """Returns the index of the group the given channel belongs to."""
    channels_per_group = MCFD16.num_channels / MCFD16.num_groups
    return int(math.floor(channel_idx/channels_per_group))

class MCFD16(app_model.Device):
    idcs                    = (26, )
    num_channels            = 16
    num_groups              = 8

    # rc value -> gain factor
    gain_factors            = { 0: 1, 1: 3, 2: 10 }

    # mapping of gain rc values to maximum thresholds in mV
    max_threshold_by_gain   = { 0: 250.0, 1: 75.0, 2: 25.0 }

    # rc value -> fraction
    cfd_fractions           = { 0: '20%', 1: '40%' }

    # trigger index -> trigger name
    trigger_names           = { 0: 'front', 1: 'rear1', 2: 'rear2' }

    # test pulser frequencies
    test_pulser_enum        = { 0: 'off', 1: '2.5 MHz', 2: '1.22 kHz' }

    # rate measurement time base values [s]
    time_base_secs          = { 0: 1/8.0, 3: 1/4.0, 7: 1/2.0, 15: 1.0 }

    # limits of the SIP-7 delay chips [ns]
    delay_chip_limits_ns    = (5, 100)

    # number of taps of the delay chips
    delay_chip_taps         = 5

    # the default delay chip max delay [ns]
    default_delay_chip      = 20

    conv_table_coincidence_ns = {
            3: 4, 4: 5, 5: 5, 6: 5, 7: 6, 8: 6, 9: 6, 10: 6, 11: 6, 12: 6, 13:
            7, 14: 7, 15: 7, 16: 8, 17: 10, 18: 11, 19: 12, 20: 12, 21: 15, 22:
            17, 23: 17, 24: 19, 25: 21, 26: 24, 27: 26, 28: 29, 29: 31, 30: 34,
            31: 36, 32: 39, 33: 41, 34: 44, 35: 47, 36: 49, 37: 52, 38: 55, 39:
            57, 40: 60, 41: 63, 42: 66, 43: 68, 44: 71, 45: 74, 46: 77, 47: 80,
            48: 83, 49: 86, 50: 89, 51: 89, 52: 92, 53: 95, 54: 98, 55: 101,
            56: 104, 57: 108, 58: 111, 59: 114, 60: 117, 61: 121, 62: 124, 63:
            127, 64: 131, 65: 134, 66: 138, 67: 141, 68: 145, 69: 149, 70: 152,
            71: 156, 72: 160, 73: 164, 74: 167, 75: 171, 76: 175, 77: 179, 78:
            183, 79: 187, 80: 191, 81: 196, 82: 200, 83: 204, 84: 209, 85: 213,
            86: 218, 87: 222, 88: 227, 89: 231, 90: 236, 91: 241, 92: 246, 93:
            251, 94: 256, 95: 261, 96: 266, 97: 272, 98: 277, 99: 283, 100:
            288, 101: 294, 102: 300, 103: 306, 104: 312, 105: 318, 106: 324,
            107: 330, 108: 337, 109: 344, 110: 350, 111: 357, 112: 364, 113:
            372, 114: 379, 115: 387, 116: 394, 117: 402, 118: 411, 119: 419,
            120: 428, 121: 436, 122: 445, 123: 455, 124: 464, 125: 474, 126:
            485, 127: 495, 128: 506, 129: 518, 130: 529, 131: 542, 132: 554,
            133: 568, 134: 581, 135: 596, 136: 611}

    conv_table_deadtime_ns = {
            27: 20, 28: 21, 29: 23, 30: 25, 31: 26, 32: 28, 33: 30, 34: 31, 35:
            33, 36: 35, 37: 36, 38: 38, 39: 40, 40: 41, 41: 43, 42: 45, 43: 46,
            44: 48, 45: 50, 46: 52, 47: 53, 48: 55, 49: 57, 50: 59, 51: 61, 52:
            62, 53: 64, 54: 66, 55: 68, 56: 70, 57: 71, 58: 73, 59: 75, 60: 77,
            61: 79, 62: 81, 63: 83, 64: 85, 65: 87, 66: 88, 67: 90, 68: 92, 69:
            94, 70: 96, 71: 98, 72: 100, 73: 102, 74: 104, 75: 106, 76: 108,
            77: 110, 78: 112, 79: 114, 80: 116, 81: 118, 82: 121, 83: 123, 84:
            125, 85: 127, 86: 129, 87: 131, 88: 133, 89: 135, 90: 138, 91: 140,
            92: 142, 93: 144, 94: 146, 95: 149, 96: 151, 97: 153, 98: 156, 99:
            158, 100: 160, 101: 162, 102: 165, 103: 167, 104: 170, 105: 172,
            106: 174, 107: 177, 108: 179, 109: 182, 110: 184, 111: 186, 112:
            189, 113: 191, 114: 194, 115: 197, 116: 199, 117: 202, 118: 204,
            119: 207, 120: 209, 121: 212, 122: 215, 123: 217, 124: 220, 125:
            223, 126: 226, 127: 228, 128: 231, 129: 234, 130: 237, 131: 239,
            132: 242, 133: 245, 134: 248, 135: 251, 136: 254, 137: 257, 138:
            260, 139: 263, 140: 266, 141: 269, 142: 272, 143: 275, 144: 278,
            145: 281, 146: 285, 147: 288, 148: 291, 149: 294, 150: 298, 151:
            301, 152: 304, 153: 308, 154: 311, 155: 314, 156: 318, 157: 321,
            158: 325, 159: 328, 160: 332, 161: 336, 162: 339, 163: 343, 164:
            347, 165: 350, 166: 354, 167: 358, 168: 362, 169: 366, 170: 370,
            171: 374, 172: 378, 173: 382, 174: 386, 175: 390, 176: 394, 177:
            399, 178: 403, 179: 407, 180: 412, 181: 416, 182: 421, 183: 425,
            184: 430, 185: 434, 186: 439, 187: 444, 188: 449, 189: 454, 190:
            459, 191: 464, 192: 469, 193: 474, 194: 479, 195: 484, 196: 490,
            197: 495, 198: 501, 199: 506, 200: 512, 201: 518, 202: 524, 203:
            530, 204: 536, 205: 542, 206: 548, 207: 554, 208: 561, 209: 567,
            210: 574, 211: 581, 212: 587, 213: 594, 214: 602, 215: 609, 216:
            616, 217: 624, 218: 632, 219: 639, 220: 647, 221: 656, 222: 664}

    conv_table_gategen_ns = {
            5: 20, 6: 20, 7: 20, 8: 20, 9: 21, 10: 22, 11: 23, 12: 24, 13: 26,
            14: 27, 15: 28, 16: 30, 17: 31, 18: 32, 19: 34, 20: 35, 21: 36, 22:
            37, 23: 39, 24: 40, 25: 42, 26: 43, 27: 44, 28: 46, 29: 47, 30: 48,
            31: 50, 32: 51, 33: 52, 34: 54, 35: 55, 36: 57, 37: 58, 38: 59, 39:
            61, 40: 62, 41: 64, 42: 65, 43: 67, 44: 68, 45: 70, 46: 71, 47: 73,
            48: 74, 49: 76, 50: 77, 51: 79, 52: 80, 53: 82, 54: 83, 55: 85, 56:
            86, 57: 88, 58: 89, 59: 91, 60: 92, 61: 94, 62: 96, 63: 97, 64: 99,
            65: 100, 66: 102, 67: 104, 68: 105, 69: 107, 70: 108, 71: 110, 72:
            112, 73: 113, 74: 115, 75: 117, 76: 119, 77: 120, 78: 122, 79: 124,
            80: 125, 81: 127, 82: 129, 83: 131, 84: 132, 85: 134, 86: 136, 87:
            138, 88: 140, 89: 141, 90: 143, 91: 145, 92: 147, 93: 149, 94: 151,
            95: 153, 96: 154, 97: 156, 98: 158, 99: 160, 100: 162, 101: 164,
            102: 166, 103: 168, 104: 170, 105: 172, 106: 174, 107: 176, 108:
            178, 109: 180, 110: 182, 111: 184, 112: 186, 113: 188, 114: 190,
            115: 193, 116: 195, 117: 197, 118: 199, 119: 201, 120: 203, 121:
            206, 122: 208, 123: 210, 124: 212, 125: 215, 126: 217, 127: 219,
            128: 221, 129: 224, 130: 226, 131: 229, 132: 231, 133: 233, 134:
            236, 135: 238, 136: 241, 137: 243, 138: 246, 139: 248, 140: 251,
            141: 253, 142: 256, 143: 258, 144: 261, 145: 264, 146: 266, 147:
            269, 148: 272, 149: 274, 150: 277, 151: 280, 152: 283, 153: 285,
            154: 288, 155: 291, 156: 294, 157: 297, 158: 300, 159: 303, 160:
            306, 161: 309, 162: 312, 163: 315, 164: 318, 165: 321, 166: 324,
            167: 327, 168: 331, 169: 334, 170: 337, 171: 340, 172: 344, 173:
            347, 174: 351, 175: 354, 176: 358, 177: 361, 178: 365, 179: 368,
            180: 372, 181: 376, 182: 379, 183: 383, 184: 387, 185: 391, 186:
            395, 187: 399, 188: 403, 189: 407, 190: 411, 191: 415, 192: 419,
            193: 423, 194: 428, 195: 432, 196: 436, 197: 441, 198: 445, 199:
            450, 200: 455, 201: 460, 202: 464, 203: 469, 204: 474, 205: 479,
            206: 484, 207: 490, 208: 495, 209: 500, 210: 506, 211: 511, 212:
            517, 213: 523, 214: 528, 215: 534, 216: 540, 217: 547, 218: 553,
            219: 559, 220: 566, 221: 572, 222: 579, 223: 586, 224: 593, 225:
            600, 226: 608, 227: 615, 228: 623, 229: 631, 230: 639, 231: 648,
            232: 656, 233: 665, 234: 674, 235: 683, 236: 693, 237: 703, 238:
            713, 239: 723, 240: 734, 241: 745, 242: 757, 243: 769, 244: 781,
            245: 794, 246: 808, 247: 822, 248: 836, 249: 852, 250: 868, 251:
            885, 252: 902, 253: 921, 254: 941, 255: 962}

    conv_table_width_ns = {
            16: 6, 17: 6, 18: 6, 19: 6, 20: 9, 21: 10, 22: 12, 23: 13, 24: 15,
            25: 17, 26: 18, 27: 20, 28: 21, 29: 23, 30: 25, 31: 26, 32: 28, 33:
            30, 34: 31, 35: 33, 36: 35, 37: 36, 38: 38, 39: 40, 40: 41, 41: 43,
            42: 45, 43: 46, 44: 48, 45: 50, 46: 52, 47: 53, 48: 55, 49: 57, 50:
            59, 51: 61, 52: 62, 53: 64, 54: 66, 55: 68, 56: 70, 57: 71, 58: 73,
            59: 75, 60: 77, 61: 79, 62: 81, 63: 83, 64: 85, 65: 87, 66: 88, 67:
            90, 68: 92, 69: 94, 70: 96, 71: 98, 72: 100, 73: 102, 74: 104, 75:
            106, 76: 108, 77: 110, 78: 112, 79: 114, 80: 116, 81: 118, 82: 121,
            83: 123, 84: 125, 85: 127, 86: 129, 87: 131, 88: 133, 89: 135, 90:
            138, 91: 140, 92: 142, 93: 144, 94: 146, 95: 149, 96: 151, 97: 153,
            98: 156, 99: 158, 100: 160, 101: 162, 102: 165, 103: 167, 104: 170,
            105: 172, 106: 174, 107: 177, 108: 179, 109: 182, 110: 184, 111:
            186, 112: 189, 113: 191, 114: 194, 115: 197, 116: 199, 117: 202,
            118: 204, 119: 207, 120: 209, 121: 212, 122: 215, 123: 217, 124:
            220, 125: 223, 126: 226, 127: 228, 128: 231, 129: 234, 130: 237,
            131: 239, 132: 242, 133: 245, 134: 248, 135: 251, 136: 254, 137:
            257, 138: 260, 139: 263, 140: 266, 141: 269, 142: 272, 143: 275,
            144: 278, 145: 281, 146: 285, 147: 288, 148: 291, 149: 294, 150:
            298, 151: 301, 152: 304, 153: 308, 154: 311, 155: 314, 156: 318,
            157: 321, 158: 325, 159: 328, 160: 332, 161: 336, 162: 339, 163:
            343, 164: 347, 165: 350, 166: 354, 167: 358, 168: 362, 169: 366,
            170: 370, 171: 374, 172: 378, 173: 382, 174: 386, 175: 390, 176:
            394, 177: 399, 178: 403, 179: 407, 180: 412, 181: 416, 182: 421,
            183: 425, 184: 430, 185: 434, 186: 439, 187: 444, 188: 449, 189:
            454, 190: 459, 191: 464, 192: 469, 193: 474, 194: 479, 195: 484,
            196: 490, 197: 495, 198: 501, 199: 506, 200: 512, 201: 518, 202:
            524, 203: 530, 204: 536, 205: 542, 206: 548, 207: 554, 208: 561,
            209: 567, 210: 574, 211: 581, 212: 587, 213: 594, 214: 602, 215:
            609, 216: 616, 217: 624, 218: 632, 219: 639, 220: 647, 221: 656,
            222: 664}

    
    trigger_pattern_changed = pyqtSignal(int, int)  # trigger index, pattern value
    pair_pattern_changed    = pyqtSignal(int, int)  # pattern index, pattern value
    single_channel_mode_changed = pyqtSignal(bool)

    delay_chip_ns_changed = pyqtSignal(int) # delay in ns

    def __init__(self, device_model=None, device_config=None, device_profile=None, parent=None):
        super(MCFD16, self).__init__(device_model=device_model, device_config=device_config,
                device_profile=device_profile, parent=parent)

        self.log = util.make_logging_source_adapter(__name__, self)
        self._delay_chip_ns = MCFD16.default_delay_chip
        self.parameter_changed[object].connect(self._on_parameter_changed)

    def propagate_state(self):
        """Propagate the current state using the signals defined in this class."""
        if not self.has_model():
            return

        for param_profile in self.profile.parameters:
            if self.has_parameter(param_profile.address):
                self.parameter_changed[object].emit(self.make_bound_parameter(param_profile.address))

    def _on_parameter_changed(self, bp):
        if bp.name is None:
            return

        if re.match(r'trigger_pattern\d_.+', bp.name):
            # When the device memory if being fetched for the first time these
            # methods will throw as one of the two memory cells will not be
            # present yet.
            try:
                self.trigger_pattern_changed.emit(bp.index, self.get_trigger_pattern(bp.index))
            except KeyError:
                pass

        elif re.match(r'pair_pattern\d+_.+', bp.name):
            try:
                self.pair_pattern_changed.emit(bp.index, self.get_pair_pattern(bp.index))
            except KeyError:
                pass

        elif bp.name == 'single_channel_mode':
            self.single_channel_mode_changed.emit(bp.value)

        elif bp.name == 'discriminator_mode':
            # Refresh the fast_veto register on discriminator mode change
            self.read_parameter(self.profile['fast_veto'].address)

    def get_trigger_pattern(self, trigger_index):
        high = self.get_parameter_by_name('trigger_pattern%d_high' % trigger_index)
        low  = self.get_parameter_by_name('trigger_pattern%d_low'  % trigger_index)

        return (high << 8) | low

    def set_trigger_pattern(self, trigger_index, pattern):
        high = (pattern & 0xFF00) >> 8
        low  = pattern & 0x00FF
        self.set_parameter_by_name('trigger_pattern%d_high' % trigger_index, high)
        self.set_parameter_by_name('trigger_pattern%d_low'  % trigger_index, low)

    def get_pair_pattern(self, pattern_index):
        high = self.get_parameter_by_name('pair_pattern%d_high' % pattern_index)
        low  = self.get_parameter_by_name('pair_pattern%d_low'  % pattern_index)

        return (high << 8) | low

    def set_pair_pattern(self, pattern_index, pattern):
        high = (pattern & 0xFF00) >> 8
        low  = pattern & 0x00FF
        self.set_parameter_by_name('pair_pattern%d_high' % pattern_index, high)
        self.set_parameter_by_name('pair_pattern%d_low'  % pattern_index, low)

    def get_effective_delay(self, group_or_common):
        if group_or_common == 'common':
            register_value = self.get_parameter_by_name('delay_common')
        else:
            register_value = self.get_parameter_by_name('delay_group%d' % int(group_or_common))

        return self.get_delay_chip_ns() / MCFD16.delay_chip_taps * (register_value+1)

    def get_effective_threshold_mV(self, channel_idx_or_common):
        """Returns the effective threshold in mV for the given channel.
        The parameter channel_idx_or_common must be a numeric channel idx or
        the string 'common'. If any of the required device memory values are
        not known this method will throw.
        """
        if channel_idx_or_common == 'common':
            gain_param      = 'gain_common'
            threshold_param = 'threshold_common'
        else:
            gain_param      = 'gain_group%d' % channel_to_group(channel_idx_or_common)
            threshold_param = 'threshold_channel%d' % channel_idx_or_common

        gain      = self.get_parameter_by_name(gain_param)
        threshold = self.get_parameter_by_name(threshold_param)

        max_threshold_mv  = MCFD16.max_threshold_by_gain[gain]
        threshold_step_mv = max_threshold_mv / 255
        threshold_mv      = threshold_step_mv * threshold

        return threshold_mv

    def get_polarity(self, group):
        """Returns the polarity for the given group.
        Group is either a numeric group index or the word 'common'.
        """
        name = 'polarity_common' if group == 'common' else 'polarity_group%d' % group
        return self[name]

    def set_polarity(self, group, polarity):
        name = 'polarity_common' if group == 'common' else 'polarity_group%d' % group
        self.set_parameter_by_name(name, polarity)

    def toggle_polarity(self, group):
        pol = self.get_polarity(group)
        self.set_polarity(group, Polarity.positive if pol == Polarity.negative else Polarity.negative)

    def set_single_channel_mode(self, value, response_handler=None):
        return self.set_parameter('single_channel_mode', value, response_handler=response_handler)

    # Extensions
    @modifies_extensions
    def set_delay_chip_ns(self, value):
        self._delay_chip_ns = int(value)
        self.delay_chip_ns_changed.emit(self.delay_chip_ns)

    def get_delay_chip_ns(self):
        return self._delay_chip_ns

    delay_chip_ns = pyqtProperty(int, get_delay_chip_ns, set_delay_chip_ns, notify=delay_chip_ns_changed)

    def get_extensions(self):
        return [('delay_chip_ns', self.delay_chip_ns)]

dynamic_label_style = "QLabel { background-color: lightgrey; }"

def make_dynamic_label(initial_value="", longest_value=None, fixed_width=True, fixed_height=False,
        alignment=Qt.AlignRight | Qt.AlignVCenter):
    """Creates a label used for displaying dynamic values.
    The labels initial text is given by `initial_value'.  If longest_value is a
    non-empty string it is used to calculate the maximum size of the label. If
    fixed_width is True the labels width will be set to the maximum width, if
    fixed_height is True the labels height will be set to the maximum height.
    """
    ret = QtGui.QLabel()
    ret.setStyleSheet(dynamic_label_style)
    ret.setAlignment(alignment)

    if longest_value is not None and (fixed_width or fixed_height):
        ret.setText(str(longest_value))
        size = ret.sizeHint()
        if fixed_width:
            ret.setFixedWidth(size.width())
        if fixed_height:
            ret.setFixedHeight(size.height())

    ret.setText(initial_value)

    return ret

class ChannelMaskWidget(QtGui.QGroupBox):
    value_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super(ChannelMaskWidget, self).__init__("Channel Mask", parent)

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        self.checkboxes = list()

        for i in range(MCFD16.num_groups):
            cb = QtGui.QCheckBox()
            r  = group_channel_range(MCFD16.num_groups-i-1)
            l  = QtGui.QLabel("%d\n%d" % (r[1], r[0]))
            f  = l.font()
            f.setPointSize(8)
            l.setFont(f)

            self.checkboxes.append(cb)

            layout.addWidget(cb, 0, i+1, 1, 1, Qt.AlignCenter)
            layout.addWidget(l,  1, i+1, 1, 1, Qt.AlignCenter)

        self.result_label = make_dynamic_label(initial_value="0", longest_value=str(2**MCFD16.num_groups-1))

        layout.addWidget(self.result_label, 0, layout.columnCount())

        self.checkboxes = list(reversed(self.checkboxes))

        self._helper = BitPatternHelper(self.checkboxes, self)
        self._helper.value_changed.connect(self.value_changed)
        self._helper.value_changed.connect(self._on_value_changed)

    def _on_cb_stateChanged(self, state):
        value = self.value
        self.value_changed.emit(value)

    def get_value(self):
        return self._helper.value

    def set_value(self, value):
        self._helper.value = value

    def _on_value_changed(self, value):
        self.result_label.setText(str(value))

    value = pyqtProperty(int, get_value, set_value, notify=value_changed)

class PreampPage(QtGui.QGroupBox):
    polarity_button_size = QtCore.QSize(20, 20)

    def __init__(self, device, context, parent=None):
        super(PreampPage, self).__init__("Preamp", parent)
        self.device  = device
        self.context = context

        self.icon_pol_positive = QtGui.QIcon(QtGui.QPixmap(context.find_data_file('mesycontrol/ui/list-add.png'))
                .scaled(PreampPage.polarity_button_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.icon_pol_negative = QtGui.QIcon(QtGui.QPixmap(context.find_data_file('mesycontrol/ui/list-remove.png'))
                .scaled(PreampPage.polarity_button_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        self.pol_common = QtGui.QPushButton(self.icon_pol_positive, QtCore.QString())
        self.pol_common.setMaximumSize(PreampPage.polarity_button_size)
        self.pol_common.clicked.connect(self._on_pb_polarity_clicked)
        self.pol_inputs = list()

        gain_min_max     = device.profile['gain_common'].range.to_tuple()
        self.gain_common = make_spinbox(limits=gain_min_max)
        self.gain_common.valueChanged.connect(self._on_gain_value_changed)
        self.gain_label_common = make_dynamic_label(longest_value=MCFD16.gain_factors[gain_min_max[1]])
        self.gain_inputs = list()
        self.gain_labels = list()

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        offset = 0
        layout.addWidget(QtGui.QLabel("Common"),    offset, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(self.pol_common,           offset, 1, 1, 1, Qt.AlignCenter)
        layout.addWidget(self.gain_common,          offset, 2)
        layout.addWidget(self.gain_label_common,    offset, 3)

        offset += 1
        layout.addWidget(make_title_label("Group"),    offset, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Polarity"), offset, 1)
        layout.addWidget(make_title_label("Gain"),     offset, 2, 1, 2, Qt.AlignCenter)

        for i in range(MCFD16.num_groups):
            offset      = layout.rowCount()
            group_range = group_channel_range(i)
            group_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1])) 
            pol_button  = QtGui.QPushButton(self.icon_pol_positive, QtCore.QString())
            pol_button.clicked.connect(self._on_pb_polarity_clicked)
            pol_button.setMaximumSize(PreampPage.polarity_button_size)
            gain_spin   = make_spinbox(limits=gain_min_max)
            gain_spin.valueChanged.connect(self._on_gain_value_changed)
            gain_label  = make_dynamic_label(longest_value=MCFD16.gain_factors[gain_min_max[1]])

            self.pol_inputs.append(pol_button)
            self.gain_inputs.append(gain_spin)
            self.gain_labels.append(gain_label)

            layout.addWidget(group_label,   offset, 0, 1, 1, Qt.AlignRight)
            layout.addWidget(pol_button,    offset, 1, 1, 1, Qt.AlignCenter)
            layout.addWidget(gain_spin,     offset, 2)
            layout.addWidget(gain_label,    offset, 3)

        layout.addWidget(hline(), layout.rowCount(), 0, 1, 4) # hline separator

        self.cb_bwl = QtGui.QCheckBox("BWL enable")
        self.cb_bwl.stateChanged.connect(self._on_cb_bwl_state_changed)
        self.cb_bwl.setToolTip("Bandwidth limit enable")
        self.cb_bwl.setStatusTip(self.cb_bwl.toolTip())

        layout.addWidget(self.cb_bwl, layout.rowCount(), 2, 1, 2)

        device.parameter_changed[object].connect(self._on_device_parameter_changed)

    # Device changes
    def _on_device_parameter_changed(self, bp):
        if bp.name is None:
            return

        if bp.name == 'polarity_common' or re.match(r'polarity_group\d', bp.name):
            icon = (self.icon_pol_positive if bp.value == Polarity.positive
                    else self.icon_pol_negative)
            button = self.pol_inputs[bp.index] if bp.has_index() else self.pol_common
            button.setIcon(icon)

        elif bp.name == 'gain_common' or re.match(r'gain_group\d', bp.name):
            spin  = self.gain_inputs[bp.index] if bp.has_index() else self.gain_common
            label = self.gain_labels[bp.index] if bp.has_index() else self.gain_label_common
            with util.block_signals(spin):
                spin.setValue(bp.value)

            label.setText(str(MCFD16.gain_factors[bp.value]))

        elif bp.name == 'bwl_enable':
            with util.block_signals(self.cb_bwl):
                self.cb_bwl.setChecked(bp.value)

    # GUI changes
    def _on_pb_polarity_clicked(self):
        pb = self.sender()
        group = 'common' if pb == self.pol_common else self.pol_inputs.index(pb)
        self.device.toggle_polarity(group)

        #pb = self.sender()
        #if pb == self.pol_common:
        #    name = 'polarity_common'
        #else:
        #    name = 'polarity_group%d' % self.pol_inputs.index(pb)

        #value = Polarity.negative if self.device[name] == Polarity.positive else Polarity.negative

        #self.device.set_parameter_by_name(name, value)

    def _on_gain_value_changed(self, value):
        pb = self.sender()
        if pb == self.gain_common:
            name = 'gain_common'
        else:
            name = 'gain_group%d' % self.gain_inputs.index(pb)

        self.device.set_parameter_by_name(name, value)

    def _on_cb_bwl_state_changed(self, state):
        self.device.set_parameter_by_name('bwl_enable', int(self.cb_bwl.isChecked()))

def make_fraction_combo():
    ret = QtGui.QComboBox()

    for k in sorted(MCFD16.cfd_fractions.keys()):
        ret.addItem(MCFD16.cfd_fractions[k], k)

    return ret

class DiscriminatorPage(QtGui.QGroupBox):
    def __init__(self, device, context, parent=None):
        super(DiscriminatorPage, self).__init__("Discriminator", parent)
        self.device  = device
        self.context = context

        # 1st row:  CFD/LE choice
        # 2nd row: common delay, fraction, threshold
        # 3rd row: column headers
        # following 16:  8 delays, 8 fractions, 16 thresholds
        # last row    : delay chip max delay

        delay_limits     = device.profile['delay_common'].range.to_tuple()
        threshold_limits = device.profile['threshold_common'].range.to_tuple()

        self.delay_common               = make_spinbox(limits=delay_limits, prefix='Tap ')
        self.delay_common.valueChanged.connect(self._on_delay_input_valueChanged)
        self.delay_label_common         = make_dynamic_label(longest_value='%d ns' % MCFD16.delay_chip_limits_ns[1])
        self.fraction_common            = make_fraction_combo()
        self.fraction_common.currentIndexChanged.connect(self._on_fraction_currentIndexChanged)
        self.threshold_common           = make_spinbox(limits=threshold_limits)
        self.threshold_common.valueChanged.connect(self._on_threshold_input_valueChanged)
        self.threshold_label_common = make_dynamic_label(longest_value='%.2f mV' % max(MCFD16.max_threshold_by_gain.values()))

        self.delay_inputs       = list()
        self.delay_labels       = list()
        self.fraction_inputs    = list()
        self.threshold_inputs   = list()
        self.threshold_labels   = list()

        self.rb_mode_cfd = QtGui.QRadioButton("CFD", toggled=self._on_rb_mode_cfd_toggled)
        self.rb_mode_le  = QtGui.QRadioButton("LE")

        mode_label  = QtGui.QLabel("Mode:")
        mode_layout = QtGui.QHBoxLayout()
        mode_layout.setSpacing(4)
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.rb_mode_cfd)
        mode_layout.addWidget(self.rb_mode_le)
        mode_layout.addStretch(1)

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        offset = layout.rowCount()
        layout.addLayout(mode_layout, offset, 0, 1, 7)

        layout.addWidget(hline(), layout.rowCount(), 0, 1, 7) # hline separator

        offset = layout.rowCount()
        layout.addWidget(QtGui.QLabel("Common"),        offset, 0, 1, 1, Qt.AlignCenter)
        layout.addWidget(self.delay_common,             offset, 1)
        layout.addWidget(self.delay_label_common,       offset, 2)
        layout.addWidget(self.fraction_common,          offset, 3)
        layout.addWidget(QtGui.QLabel("Common"),        offset, 4)
        layout.addWidget(self.threshold_common,         offset, 5)
        layout.addWidget(self.threshold_label_common,   offset, 6)

        offset = layout.rowCount()
        layout.addWidget(make_title_label("Group"),     offset, 0)
        layout.addWidget(make_title_label("Delay"),     offset, 1, 1, 2, Qt.AlignCenter)
        layout.addWidget(make_title_label("Fraction"),  offset, 3)
        layout.addWidget(make_title_label("Chan"),   offset, 4)
        layout.addWidget(make_title_label("Threshold"), offset, 5, 1, 2, Qt.AlignCenter)

        for i in range(MCFD16.num_channels):
            channels_per_group  = MCFD16.num_channels / MCFD16.num_groups
            group               = int(i / channels_per_group)
            group_range         = group_channel_range(group)
            offset              = layout.rowCount()

            if i % channels_per_group == 0:
                group_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1])) 
                delay_input = make_spinbox(limits=delay_limits, prefix='Tap ')
                delay_input.valueChanged.connect(self._on_delay_input_valueChanged)
                delay_label = make_dynamic_label(longest_value='%d ns' % MCFD16.delay_chip_limits_ns[1])
                fraction_input = make_fraction_combo()
                fraction_input.currentIndexChanged.connect(self._on_fraction_currentIndexChanged)

                self.delay_inputs.append(delay_input)
                self.delay_labels.append(delay_label)
                self.fraction_inputs.append(fraction_input)
                
                layout.addWidget(group_label,           offset, 0, 1, 1, Qt.AlignRight)
                layout.addWidget(delay_input,           offset, 1)
                layout.addWidget(delay_label,           offset, 2)
                layout.addWidget(fraction_input,        offset, 3)

            threshold_input = make_spinbox(limits=threshold_limits)
            threshold_input.valueChanged.connect(self._on_threshold_input_valueChanged)
            threshold_label = make_dynamic_label(longest_value='%.2f mV' % max(MCFD16.max_threshold_by_gain.values()))

            self.threshold_inputs.append(threshold_input)
            self.threshold_labels.append(threshold_label)

            layout.addWidget(QtGui.QLabel("%d" % i),    offset, 4, 1, 1, Qt.AlignRight)
            layout.addWidget(threshold_input,           offset, 5)
            layout.addWidget(threshold_label,           offset, 6)

        layout.addWidget(hline(), layout.rowCount(), 0, 1, 7) # hline separator

        # Delay chip
        self.delay_chip_input = make_spinbox(limits=MCFD16.delay_chip_limits_ns, suffix=' ns', single_step=5,
                value = device.get_delay_chip_ns())
        self.delay_chip_input.valueChanged.connect(self._on_delay_chip_input_valueChanged)

        delay_chip_label = QtGui.QLabel("Delay chip")
        delay_chip_layout = QtGui.QHBoxLayout()
        delay_chip_layout.setSpacing(4)
        delay_chip_layout.addWidget(delay_chip_label)
        delay_chip_layout.addWidget(self.delay_chip_input)
        delay_chip_layout.addStretch(1)

        layout.addLayout(delay_chip_layout, layout.rowCount(), 0, 1, 7)

        # Fast veto
        self.cb_fast_veto = QtGui.QCheckBox("Fast veto")
        self.cb_fast_veto.stateChanged.connect(self._on_cb_fast_veto_stateChanged)
        layout.addWidget(self.cb_fast_veto, layout.rowCount(), 0, 1, 7)

        device.parameter_changed[object].connect(self._on_device_parameter_changed)
        device.delay_chip_ns_changed.connect(self._on_device_delay_chip_ns_changed)

    # Device changes
    def _on_device_parameter_changed(self, bp):
        if bp.name is None:
            return

        if bp.name == 'discriminator_mode':
            rb = self.rb_mode_cfd if bp.value == DiscriminatorMode.cfd else self.rb_mode_le
            with util.block_signals(rb):
                rb.setChecked(True)

        elif bp.name == 'delay_common' or re.match(r'delay_group\d', bp.name):
            spin  = self.delay_inputs[bp.index] if bp.has_index() else self.delay_common
            with util.block_signals(spin):
                spin.setValue(bp.value)

            label = self.delay_labels[bp.index] if bp.has_index() else self.delay_label_common
            self._update_delay_label(label, bp.index if bp.has_index() else 'common')

        elif bp.name == 'fraction_common' or re.match(r'fraction_group\d', bp.name):
            combo = self.fraction_inputs[bp.index] if bp.has_index() else self.fraction_common
            with util.block_signals(combo):
                combo.setCurrentIndex(bp.value)

        elif bp.name == 'threshold_common' or re.match(r'threshold_channel\d+', bp.name):
            spin = self.threshold_inputs[bp.index] if bp.has_index() else self.threshold_common
            with util.block_signals(spin):
                spin.setValue(bp.value)

            label = self.threshold_labels[bp.index] if bp.has_index() else self.threshold_label_common
            print "threshold change: updating threshold for channel", bp.index if bp.has_index() else 'common'
            self._update_threshold_label(label, bp.index if bp.has_index() else 'common')

        elif bp.name == 'gain_common' or re.match(r'gain_group\d', bp.name):
            if bp.has_index():
                channel_range = group_channel_range(bp.index)
                for channel in channel_range:
                    print "gain change: updating threshold for channel", channel
                    label = self.threshold_labels[channel]
                    self._update_threshold_label(label, channel)
            else:
                print "gain change: updating threshold for channel common"
                self._update_threshold_label(self.threshold_label_common, 'common')

        elif bp.name == 'fast_veto':
            cb = self.cb_fast_veto
            with util.block_signals(cb):
                cb.setChecked(bool(bp.value))

    def _update_delay_label(self, label, group_or_common):
        label.setText("%d ns" % self.device.get_effective_delay(group_or_common))

    def _update_threshold_label(self, label, channel_idx_or_common):
        et = self.device.get_effective_threshold_mV(channel_idx_or_common)
        print "_update_threshold_label", channel_idx_or_common, et
        label.setText("%.2f mV" % et)

    def _on_device_delay_chip_ns_changed(self, value):
        spin = self.delay_chip_input
        with util.block_signals(spin):
            spin.setValue(value)
        self._update_delay_label(self.delay_label_common, 'common')
        for i in range(MCFD16.num_groups):
            self._update_delay_label(self.delay_labels[i], i)

    # GUI changes
    @pyqtSlot(bool)
    def _on_rb_mode_cfd_toggled(self, on_off):
        value = DiscriminatorMode.cfd if on_off else DiscriminatorMode.le
        self.device.set_parameter_by_name('discriminator_mode', value)

    def _on_delay_input_valueChanged(self, value):
        s = self.sender()
        if s == self.delay_common:
            name = 'delay_common'
        else:
            name = 'delay_group%d' % self.delay_inputs.index(s)

        self.device.set_parameter_by_name(name, value)

    def _on_delay_chip_input_valueChanged(self, value):
        self.device.delay_chip_ns = value

    def _on_fraction_currentIndexChanged(self, idx):
        s = self.sender()
        if s == self.fraction_common:
            name = 'fraction_common'
        else:
            name = 'fraction_group%d' % self.fraction_inputs.index(s)

        self.device.set_parameter_by_name(name, idx)

    def _on_threshold_input_valueChanged(self, value):
        s = self.sender()
        if s == self.threshold_common:
            name = 'threshold_common'
        else:
            name = 'threshold_channel%d' % self.threshold_inputs.index(s)

        self.device.set_parameter_by_name(name, value)

    def _on_cb_fast_veto_stateChanged(self, state):
        value = 1 if self.cb_fast_veto.isChecked() else 0
        self.device.set_parameter_by_name('fast_veto', value)

class WidthAndDeadtimePage(QtGui.QGroupBox):
    def __init__(self, device, context, parent=None):
        super(WidthAndDeadtimePage, self).__init__("Width/Dead time", parent=parent)

        self.device  = device
        self.context = context

        # Columns: Group WidthInput WidthLabel DeadtimeInput DeadtimeLabel

        width_limits    = device.profile['width_common'].range.to_tuple()
        deadtime_limits = device.profile['deadtime_common'].range.to_tuple()

        width_ns_max    = MCFD16.conv_table_width_ns[width_limits[1]]
        deadtime_ns_max = MCFD16.conv_table_deadtime_ns[deadtime_limits[1]]

        self.width_common = make_spinbox(limits=width_limits)
        self.width_common.valueChanged.connect(self._on_width_input_value_changed)
        self.width_label_common = make_dynamic_label(longest_value="%d ns" % width_ns_max)

        self.deadtime_common = make_spinbox(limits=deadtime_limits)
        self.deadtime_common.valueChanged.connect(self._on_deadtime_input_value_changed)
        self.deadtime_label_common = make_dynamic_label(longest_value="%d ns" % deadtime_ns_max)

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        offset = 0
        layout.addWidget(QtGui.QLabel("Common"),    offset, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(self.width_common,         offset, 1)
        layout.addWidget(self.width_label_common,   offset, 2)
        layout.addWidget(self.deadtime_common,      offset, 3)
        layout.addWidget(self.deadtime_label_common,offset, 4)

        offset += 1
        layout.addWidget(make_title_label("Group"),     offset, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Width"),     offset, 1, 1, 2, Qt.AlignCenter)
        layout.addWidget(make_title_label("Dead time"), offset, 3, 1, 2, Qt.AlignCenter)

        self.width_inputs = list()
        self.width_labels = list()
        self.deadtime_inputs = list()
        self.deadtime_labels = list()

        for i in range(MCFD16.num_groups):
            offset      = layout.rowCount()
            group_range = group_channel_range(i)
            group_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1])) 

            width_input = make_spinbox(limits=width_limits)
            width_input.valueChanged.connect(self._on_width_input_value_changed)
            width_label = make_dynamic_label(longest_value="%d ns" % width_ns_max)
            self.width_inputs.append(width_input)
            self.width_labels.append(width_label)

            deadtime_input = make_spinbox(limits=deadtime_limits)
            deadtime_input.valueChanged.connect(self._on_deadtime_input_value_changed)
            deadtime_label = make_dynamic_label(longest_value="%d ns" % deadtime_ns_max)
            self.deadtime_inputs.append(deadtime_input)
            self.deadtime_labels.append(deadtime_label)

            layout.addWidget(group_label,       offset, 0, 1, 1, Qt.AlignRight)
            layout.addWidget(width_input,       offset, 1)
            layout.addWidget(width_label,       offset, 2)
            layout.addWidget(deadtime_input,    offset, 3)
            layout.addWidget(deadtime_label,    offset, 4)

        device.parameter_changed[object].connect(self._on_device_parameter_changed)

    # Device changes
    def _on_device_parameter_changed(self, bp):
        if bp.name is None:
            return

        if bp.name == 'width_common' or re.match(r'width_group\d', bp.name):
            spin  = self.width_inputs[bp.index] if bp.has_index() else self.width_common
            label = self.width_labels[bp.index] if bp.has_index() else self.width_label_common
            
            with util.block_signals(spin):
                spin.setValue(bp.value)

            label.setText("%d ns" % MCFD16.conv_table_width_ns[bp.value])

        elif bp.name == 'deadtime_common' or re.match(r'deadtime_group\d', bp.name):
            spin  = self.deadtime_inputs[bp.index] if bp.has_index() else self.deadtime_common
            label = self.deadtime_labels[bp.index] if bp.has_index() else self.deadtime_label_common

            with util.block_signals(spin):
                spin.setValue(bp.value)

            label.setText("%d ns" % MCFD16.conv_table_deadtime_ns[bp.value])

    # GUI changes
    def _on_width_input_value_changed(self, value):
        s = self.sender()
        if s == self.width_common:
            name = 'width_common'
        else:
            name = 'width_group%d' % self.width_inputs.index(s)

        self.device.set_parameter_by_name(name, value)

    def _on_deadtime_input_value_changed(self, value):
        s = self.sender()
        if s == self.deadtime_common:
            name = 'deadtime_common'
        else:
            name = 'deadtime_group%d' % self.deadtime_inputs.index(s)

        self.device.set_parameter_by_name(name, value)

class MCFD16ControlsWidget(QtGui.QWidget):
    """Main MCFD16 controls: polarity, gain, delay, fraction, threshold, width, dead time."""
    def __init__(self, device, context, parent=None):
        super(MCFD16ControlsWidget, self).__init__(parent)
        self.device  = device
        self.context = context

        self.channel_mask_box       = ChannelMaskWidget(self)
        self.channel_mask_box.value_changed.connect(self._on_channel_mask_value_changed)
        self.preamp_page            = PreampPage(device, context, self)
        self.discriminator_page     = DiscriminatorPage(device, context, self)
        self.width_deadtime_page    = WidthAndDeadtimePage(device, context, self)

        # Channel mode
        mode_box = QtGui.QGroupBox("Channel Mode", self)
        mode_layout = QtGui.QGridLayout(mode_box)
        mode_layout.setContentsMargins(2, 2, 2, 2)
        self.rb_mode_single = QtGui.QRadioButton("Single", toggled=self._rb_mode_single_toggled)
        self.rb_mode_common = QtGui.QRadioButton("Common")
        mode_layout.addWidget(self.rb_mode_single, 0, 0)
        mode_layout.addWidget(self.rb_mode_common, 0, 1)

        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(*(4 for i in range(4)))
        layout.setSpacing(4)

        vbox = QtGui.QVBoxLayout()
        vbox.setSpacing(8)
        vbox.addWidget(self.preamp_page)
        vbox.addWidget(self.channel_mask_box)
        vbox.addStretch(1)
        layout.addItem(vbox)

        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.discriminator_page)
        vbox.addStretch(1)
        layout.addItem(vbox)

        vbox = QtGui.QVBoxLayout()
        vbox.setSpacing(8)
        vbox.addWidget(self.width_deadtime_page)
        vbox.addWidget(mode_box)
        vbox.addStretch(1)
        layout.addItem(vbox)

        device.parameter_changed[object].connect(self._on_device_parameter_changed)
        self.device.single_channel_mode_changed.connect(self._on_device_single_channel_mode_changed)

    # Device changes
    def _on_device_parameter_changed(self, bp):
        if bp.name is None:
            return

        if bp.name == 'channel_mask':
            with util.block_signals(self.channel_mask_box) as box:
                box.value = bp.value

    # Gui Changes
    def _on_channel_mask_value_changed(self, value):
        self.device.set_parameter_by_name('channel_mask', value)

    def _on_device_single_channel_mode_changed(self, value):
        rb = self.rb_mode_single if value else self.rb_mode_common
        with util.block_signals(rb):
            rb.setChecked(True)

    @pyqtSlot(bool)
    def _rb_mode_single_toggled(self, on_off):
        self.device.set_single_channel_mode(on_off)

class BitPatternHelper(QtCore.QObject):
    value_changed = pyqtSignal(int)

    def __init__(self, checkboxes, parent=None):
        super(BitPatternHelper, self).__init__(parent)
        self.checkboxes = checkboxes
        for cb in checkboxes:
            cb.stateChanged.connect(self._on_cb_stateChanged)

    def _on_cb_stateChanged(self, state):
        self.value_changed.emit(self.value)

    def get_value(self):
        ret = 0
        for i, cb in enumerate(self.checkboxes):
            if cb.isChecked():
                ret |= (1 << i)
        return ret

    def set_value(self, value):
        for i, cb in enumerate(self.checkboxes):
            with util.block_signals(cb):
                cb.setChecked(value & (1 << i))
        self.value_changed.emit(self.value)

    value = pyqtProperty(int, get_value, set_value, notify=value_changed)

class BitPatternWidget(QtGui.QWidget):
    """Horizontal layout containing a title label, n_bits checkboxes and a
    result label displaying the decimal value of the bit pattern.
    If msb_first is True the leftmost checkbox will toggle the highest valued
    bit, otherwise the lowest valued."""

    value_changed = pyqtSignal(int)

    def __init__(self, label, n_bits=16, msb_first=True, parent=None):
        super(BitPatternWidget, self).__init__(parent)
        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.title_label = QtGui.QLabel(label)
        layout.addWidget(self.title_label)

        self.checkboxes = list()
        for i in range(n_bits):
            cb = QtGui.QCheckBox()
            self.checkboxes.append(cb)
            layout.addWidget(cb)

        self.result_label = make_dynamic_label(initial_value="0", longest_value=str(2**n_bits-1))
        layout.addWidget(self.result_label)

        if msb_first:
            self.checkboxes = list(reversed(self.checkboxes))

        self._helper = BitPatternHelper(self.checkboxes, self)
        self._helper.value_changed.connect(self._on_helper_value_changed)
        self._helper.value_changed.connect(self.value_changed)

    def _on_helper_value_changed(self, value):
        self.result_label.setText(str(value))

    def get_value(self):
        return self._helper.value

    def set_value(self, value):
        self._helper.value = value

    value = pyqtProperty(int, get_value, set_value, notify=value_changed)

class TriggerSetupWidget(QtGui.QWidget):
    """MCFD16 trigger setup widget"""
    def __init__(self, device, context, parent=None):
        super(TriggerSetupWidget, self).__init__(parent)

        import pyqtgraph as pg

        self.device = device

        device.parameter_changed[object].connect(self._on_device_parameter_changed)
        device.trigger_pattern_changed.connect(self._on_device_trigger_pattern_changed)

        layout = QtGui.QGridLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(4, 4, 4, 4)

        trigger_labels  = ['OR all', 'Mult', 'PA', 'Mon0', 'Mon1', 'OR1', 'OR0', 'Veto', 'GG']
        trigger_names   = ['T0', 'T1', 'T2']
        self.trigger_checkboxes = [[] for i in range(len(trigger_names))]

        # Coincidence time
        # This needs special handling as the normal range is (3, 136) but
        # additionally 0 can be set enable overlap coincidence. To make this
        # work with a spinbox the range is set to (2, 136) with the value 2
        # being replaced by the `special value text' "overlap". When handling
        # the valueChanged signal this has to be taken into account!
        row_offset = 0
        col        = 7
        coinc_layout = QtGui.QHBoxLayout()
        coinc_layout.addWidget(QtGui.QLabel("Coincidence time:"))
        self.spin_coincidence_time = QtGui.QSpinBox()
        self.spin_coincidence_time.setRange(2, device.profile['coincidence_time'].range.max_value)
        self.spin_coincidence_time.setSpecialValueText("overlap")
        self.spin_coincidence_time.valueChanged[int].connect(self._on_spin_coincidence_value_changed)
        coinc_layout.addWidget(self.spin_coincidence_time)
        coincidence_value_max = MCFD16.conv_table_coincidence_ns[device.profile['coincidence_time'].range.to_tuple()[1]]
        self.label_coincidence_time = make_dynamic_label(longest_value="%d ns" % coincidence_value_max)
        coinc_layout.addWidget(self.label_coincidence_time)
        layout.addLayout(coinc_layout, row_offset, col, Qt.AlignLeft)

        row_offset = 1

        # Triggers
        for row, label in enumerate(trigger_labels):
            layout.addWidget(QtGui.QLabel(label), row+1+row_offset, 0)

            for col, trig in enumerate(trigger_names):
                layout.addWidget(QtGui.QLabel(trig), 0+row_offset, col+1)

                if ((label == 'Mon0' and trig == 'T2') or
                        label == 'Mon1' and trig in ('T0', 'T1')):
                    continue

                cb = QtGui.QCheckBox()
                self.trigger_checkboxes[col].append(cb)
                layout.addWidget(cb, row+1+row_offset, col+1)

        self.trigger_source_helpers = list()
        self.trigger_source_labels  = list()
        label_row = layout.rowCount()
        for i, box_list in enumerate(self.trigger_checkboxes):
            helper = BitPatternHelper(box_list)
            helper.value_changed.connect(self._on_trigger_source_helper_value_changed)
            self.trigger_source_helpers.append(helper)


            label = pg.VerticalLabel("0", forceWidth=True)
            label.setStyleSheet(dynamic_label_style)
            layout.addWidget(label, label_row, i+1)
            self.trigger_source_labels.append(label)

        # Set the label column to a fixed minimum height to work around a
        # problem with pg.VerticalLabel which does not honor setFixedSize() at
        # all and thus resizes depending on it's contents which causes ugly
        # re-layouts.
        layout.setRowMinimumHeight(label_row, 24)

        # Spacer between T2 and GG
        layout.addItem(QtGui.QSpacerItem(10, 1),
                row_offset, 4, layout.rowCount(), 1)

        gg_col = 5
        layout.addWidget(QtGui.QLabel("GG"), row_offset, gg_col)
        self.gg_checkboxes = list()

        # GG sources
        for i, label in enumerate(trigger_labels):
            if label in ('Mon1', 'GG'):
                continue

            cb = QtGui.QCheckBox()
            layout.addWidget(cb, i+1+row_offset, gg_col, 2 if trigger_labels[i] == 'Mon0' else 1, 1)
            self.gg_checkboxes.append(cb)

        self.gg_source_helper = BitPatternHelper(self.gg_checkboxes)
        self.gg_source_helper.value_changed.connect(self._on_gg_source_helper_value_changed)
        self.gg_source_label  = pg.VerticalLabel("0")
        self.gg_source_label.setStyleSheet(dynamic_label_style)
        layout.addWidget(self.gg_source_label, label_row, gg_col)

        layout.addItem(QtGui.QSpacerItem(10, 1),
                0, 6, layout.rowCount(), 1)

        # OR all label
        col = 7
        row = 2
        layout.addWidget(QtGui.QLabel("OR all channels"), row, col)

        # Multiplicity
        self.spin_mult_lo  = make_spinbox(limits=device.profile['multiplicity_lo'].range.to_tuple())
        self.spin_mult_hi  = make_spinbox(limits=device.profile['multiplicity_hi'].range.to_tuple())

        self.spin_mult_lo.valueChanged.connect(self._on_spin_mult_lo_valueChanged)
        self.spin_mult_hi.valueChanged.connect(self._on_spin_mult_hi_valueChanged)

        mult_layout = QtGui.QHBoxLayout()
        l = QtGui.QLabel("Low:")
        l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        mult_layout.addWidget(l)
        mult_layout.addWidget(self.spin_mult_lo)

        mult_layout.addSpacing(10)

        l = QtGui.QLabel("High:")
        l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        mult_layout.addWidget(l)
        mult_layout.addWidget(self.spin_mult_hi)

        row += 1
        layout.addLayout(mult_layout, row, col, Qt.AlignLeft)

        # Pair coincidence label
        row += 1
        layout.addWidget(QtGui.QLabel("Pair coincidence"), row, col)

        def make_monitor_combo():
            combo = QtGui.QComboBox()
            combo.addItems([("Channel %d" % i) for i in range(MCFD16.num_channels)])
            return combo

        # Monitor 0
        label = QtGui.QLabel("TM0")
        sz    = label.sizeHint()
        label.setFixedSize(sz)
        combo = make_monitor_combo()
        combo.currentIndexChanged.connect(self._on_monitor_combo_currentIndexChanged)
        mon_layout = QtGui.QHBoxLayout()
        mon_layout.setContentsMargins(0, 0, 0, 0)
        mon_layout.addWidget(label)
        mon_layout.addWidget(combo)
        mon_layout.addStretch(1)

        self.monitor_inputs = list()
        self.monitor_inputs.append(combo)

        row += 1
        layout.addLayout(mon_layout, row, col)

        # Monitor 1
        label = QtGui.QLabel("TM1")
        label.setFixedSize(sz)
        combo = make_monitor_combo()
        combo.currentIndexChanged.connect(self._on_monitor_combo_currentIndexChanged)
        mon_layout = QtGui.QHBoxLayout()
        mon_layout.setContentsMargins(0, 0, 0, 0)
        mon_layout.addWidget(label)
        mon_layout.addWidget(combo)
        mon_layout.addStretch(1)

        self.monitor_inputs.append(combo)

        row += 1
        layout.addLayout(mon_layout, row, col)

        # Trigger Pattern 1
        self.trigger_pattern1 = BitPatternWidget("TP1")
        self.trigger_pattern1.value_changed.connect(self._on_trigger_pattern_value_changed)
        self.trigger_pattern1.title_label.setFixedSize(sz)
        row += 1
        layout.addWidget(self.trigger_pattern1, row, col)

        # Trigger Pattern 0
        self.trigger_pattern0 = BitPatternWidget("TP0")
        self.trigger_pattern0.value_changed.connect(self._on_trigger_pattern_value_changed)
        self.trigger_pattern0.title_label.setFixedSize(sz)
        row += 1
        layout.addWidget(self.trigger_pattern0, row, col)

        # Veto
        row += 1
        layout.addWidget(QtGui.QLabel("Veto"), row, col)

        # GG delay
        self.spin_gg_le_delay = make_spinbox(limits=device.profile['gg_leading_edge_delay'].range.to_tuple())
        self.spin_gg_te_delay = make_spinbox(limits=device.profile['gg_trailing_edge_delay'].range.to_tuple())
        self.spin_gg_le_delay.valueChanged.connect(self._on_spin_gg_le_delay_valueChanged)
        self.spin_gg_te_delay.valueChanged.connect(self._on_spin_gg_te_delay_valueChanged)
        self.label_gg_le_delay = make_dynamic_label(
                longest_value="%d ns" % MCFD16.conv_table_gategen_ns[self.spin_gg_le_delay.maximum()])
        self.label_gg_te_delay = make_dynamic_label(
                longest_value="%d ns" % MCFD16.conv_table_gategen_ns[self.spin_gg_te_delay.maximum()])

        gg_delay_layout = QtGui.QHBoxLayout()

        l = QtGui.QLabel("LE delay:")
        l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        gg_delay_layout.addWidget(l)
        gg_delay_layout.addWidget(self.spin_gg_le_delay)
        gg_delay_layout.addWidget(self.label_gg_le_delay)

        gg_delay_layout.addSpacing(10)

        l = QtGui.QLabel("TE delay:")
        l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        gg_delay_layout.addWidget(l)
        gg_delay_layout.addWidget(self.spin_gg_te_delay)
        gg_delay_layout.addWidget(self.label_gg_te_delay)

        row += 1
        layout.addLayout(gg_delay_layout, row, col, Qt.AlignLeft)

        # Add expanding spacer items to the last row and column to keep widgets
        # tightly packed in the top-left corner.
        layout.addItem(QtGui.QSpacerItem(1, 1, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding),
                layout.rowCount(), 0, 1, layout.columnCount())
        layout.addItem(QtGui.QSpacerItem(1, 1, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding),
                0, layout.columnCount(), layout.rowCount(), 1)

    # GUI changes
    def _on_spin_coincidence_value_changed(self, value):
        # Correct to the overlap coincidence value if needed
        if value == self.spin_coincidence_time.minimum():
            value = 0

        self.device.set_parameter_by_name('coincidence_time', value)

    def _on_spin_mult_lo_valueChanged(self, value):
        self.device.set_parameter_by_name('multiplicity_lo', value)

    def _on_spin_mult_hi_valueChanged(self, value):
        self.device.set_parameter_by_name('multiplicity_hi', value)

    def _on_monitor_combo_currentIndexChanged(self, idx):
        p = 'monitor%d' % self.monitor_inputs.index(self.sender())
        self.device.set_parameter_by_name(p, idx)

    def _on_trigger_pattern_value_changed(self, value):
        idx = 0 if self.sender() == self.trigger_pattern0 else 1
        self.device.set_trigger_pattern(idx, value)

    def _on_spin_gg_le_delay_valueChanged(self, value):
        self.device.set_parameter_by_name('gg_leading_edge_delay', value)

    def _on_spin_gg_te_delay_valueChanged(self, value):
        self.device.set_parameter_by_name('gg_trailing_edge_delay', value)

    def _on_trigger_source_helper_value_changed(self, value):
        s = self.sender()
        idx = self.trigger_source_helpers.index(s)
        self.device.set_parameter_by_name('trigger%d' % idx, value)
        self.trigger_source_labels[idx].setText(str(value))

    def _on_gg_source_helper_value_changed(self, value):
        self.device.set_parameter_by_name('gg_sources', value)
        self.gg_source_label.setText(str(value))

    # Device state changes
    def _on_device_parameter_changed(self, bp):
        if bp.name is None:
            return

        if bp.name == 'coincidence_time':
            value = self.spin_coincidence_time.minimum() if bp.value < self.spin_coincidence_time.minimum() else bp.value
            with util.block_signals(self.spin_coincidence_time):
                self.spin_coincidence_time.setValue(value)
            text  = ("" if bp.value < self.spin_coincidence_time.minimum() else
                    "%d ns" % MCFD16.conv_table_coincidence_ns[bp.value])
            self.label_coincidence_time.setText(text)

        elif re.match('trigger\d', bp.name):
            h = self.trigger_source_helpers[bp.index]
            with util.block_signals(h):
                h.value = bp.value
            self.trigger_source_labels[bp.index].setText(str(bp.value))

        elif bp.name == 'gg_sources':
            with util.block_signals(self.gg_source_helper):
                self.gg_source_helper.value = bp.value
            self.gg_source_label.setText(str(bp.value))

        elif bp.name == 'multiplicity_lo':
            with util.block_signals(self.spin_mult_lo) as spin:
                spin.setValue(bp.value)

        elif bp.name == 'multiplicity_hi':
            with util.block_signals(self.spin_mult_hi) as spin:
                spin.setValue(bp.value)

        elif bp.name == 'monitor0':
            with util.block_signals(self.monitor_inputs[0]) as w:
                w.setCurrentIndex(bp.value)

        elif bp.name == 'monitor1':
            with util.block_signals(self.monitor_inputs[1]) as w:
                w.setCurrentIndex(bp.value)

        elif bp.name == 'gg_leading_edge_delay':
            with util.block_signals(self.spin_gg_le_delay) as w:
                w.setValue(bp.value)
            self.label_gg_le_delay.setText('%d ns' %
                    MCFD16.conv_table_gategen_ns[bp.value])

        elif bp.name == 'gg_trailing_edge_delay':
            with util.block_signals(self.spin_gg_te_delay) as w:
                w.setValue(bp.value)
            self.label_gg_te_delay.setText('%d ns' %
                    MCFD16.conv_table_gategen_ns[bp.value])

    def _on_device_trigger_pattern_changed(self, idx, pattern):
        w = self.trigger_pattern0 if idx == 0 else self.trigger_pattern1
        with util.block_signals(w):
            w.value = pattern

class PairCoincidenceSetupWidget(QtGui.QWidget):
    """Pair coincidence matrix display."""

    # Displays the lower right part of the pair coincidence matrix. Rows 0-14
    # correspond to pair coincidence registers 1-15 (register 0 is unused!).
    # The first row contains one checkbox (pair(0, 1)). Each consecutive row
    # contains one more checkbox, up to 15 in the last row.

    def __init__(self, device, context, parent=None):
        super(PairCoincidenceSetupWidget, self).__init__(parent)

        self.device = device
        device.pair_pattern_changed.connect(self._on_device_pair_pattern_changed)

        layout = QtGui.QGridLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 4, 4, 4)

        self.pattern_helpers = list()
        self.pattern_labels  = list()

        row_offset = 0

        # Checkboxes
        for row in range(15):
            bits = row+1
            cbs  = list()
            for col in range(bits):
                cb = QtGui.QCheckBox()
                cbs.append(cb)
                layout.addWidget(cb, row+row_offset, 15-col, 1, 1, Qt.AlignCenter)

            helper = BitPatternHelper(cbs)
            helper.value_changed.connect(self._on_bit_pattern_value_changed)
            self.pattern_helpers.append(helper)

        # Horizontal labels bottom
        row = layout.rowCount()
        for col in range(15):
            l = QtGui.QLabel("%d" % (14-col))
            l.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            layout.addWidget(l, row, col+1)

        label_size = QtGui.QLabel("65535").sizeHint()

        # Vertical labels
        col = layout.columnCount()
        for row in range(15):
            l = QtGui.QLabel("%d" % (row+1))
            l.setAlignment(Qt.AlignRight)
            layout.addWidget(l, row+row_offset, col)

            l_pattern = QtGui.QLabel("0")
            l_pattern.setStyleSheet(dynamic_label_style)
            l_pattern.setAlignment(Qt.AlignRight)
            l_pattern.setFixedSize(label_size)
            self.pattern_labels.append(l_pattern)
            layout.addWidget(l_pattern, row+row_offset, col+1)

    # GUI changes
    def _on_bit_pattern_value_changed(self, value):
        idx = self.pattern_helpers.index(self.sender())
        self._update_pattern_label(idx)
        self.device.set_pair_pattern(idx+1, value)

    # Device changes
    def _on_device_pair_pattern_changed(self, idx, pattern):
        print "device pair pattern changed; idx=", idx, "pattern=", pattern, hex(pattern), bin(pattern)
        if idx >= 1:
            with util.block_signals(self.pattern_helpers[idx-1]) as w:
                w.value = pattern
            self._update_pattern_label(idx-1)

    def _update_pattern_label(self, idx):
        self.pattern_labels[idx].setText(str(
            self.pattern_helpers[idx].value))

class MCFD16SetupWidget(QtGui.QWidget):
    def __init__(self, device, context, parent=None):
        super(MCFD16SetupWidget, self).__init__(parent)

        gbs = list()

        gb = QtGui.QGroupBox("Trigger setup")
        gb_layout = QtGui.QHBoxLayout(gb)
        gb_layout.setContentsMargins(0, 0, 0, 0)
        gb_layout.addWidget(TriggerSetupWidget(device, context))
        gbs.append(gb)

        gb = QtGui.QGroupBox("Pair coincidence")
        gb_layout = QtGui.QHBoxLayout(gb)
        gb_layout.setContentsMargins(0, 0, 0, 0)
        gb_layout.addWidget(PairCoincidenceSetupWidget(device, context))
        gbs.append(gb)

        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        for gb in gbs:
            h_layout = QtGui.QHBoxLayout()
            h_layout.addWidget(gb)
            h_layout.addStretch(1)
            gb_layout.setContentsMargins(0, 0, 0, 0)
            layout.addLayout(h_layout)

        layout.addStretch(1)

class MCFD16Widget(QtGui.QWidget):
    def __init__(self, device, context, parent=None):
        super(MCFD16Widget, self).__init__(parent)
        self.device  = device
        self.context = context

        toolbox = QtGui.QToolBox()
        toolbox.addItem(MCFD16ControlsWidget(device, context), "Preamp / CFD")
        toolbox.addItem(MCFD16SetupWidget(device, context), "Trigger / Coincidence Setup")

        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toolbox)

        self.device.add_default_parameter_subscription(self)
        self.device.propagate_state()

if __name__ == "__main__":
    import mock
    import signal
    import sys
    import device_profile_mcfd16

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
    device.profile = device_profile_mcfd16.get_device_profile()
    device.parameter_changed = mock.MagicMock()
    device.get_delay_chip_ns = mock.MagicMock(return_value=MCFD16.default_delay_chip)

    w = MCFD16Widget(device, context)
    w.show()

    sys.exit(app.exec_())
