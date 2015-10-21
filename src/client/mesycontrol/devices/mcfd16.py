#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import re
import itertools
import weakref

from .. qt import pyqtProperty
from .. qt import pyqtSignal
from .. qt import Qt
from .. qt import QtCore
from .. qt import QtGui
import pyqtgraph.widgets.VerticalLabel as vlabel

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

import mcfd16_profile

NUM_CHANNELS    = 16
NUM_GROUPS      =  8

# rc value -> gain factor
GAIN_FACTORS    = { 0: 1, 1: 3, 2: 10 }

# mapping of gain rc values to maximum thresholds in mV
MAX_THRESHOLD_BY_GAIN   = { 0: 250.0, 1: 75.0, 2: 25.0 }

# rc value -> fraction
CFD_FRACTIONS           = { 0: '20%', 1: '40%' }

# trigger index -> trigger name
TRIGGER_NAMES           = { 0: 'front', 1: 'rear1', 2: 'rear2' }

# test pulser frequencies
TEST_PULSER_FREQS       = { 0: 'off', 1: '2.5 MHz', 2: '1.22 kHz' }

# rate measurement time base values [s]
TIME_BASE_SECS          = { 0: 1/8.0, 3: 1/4.0, 7: 1/2.0, 15: 1.0 }

# limits of the SIP-7 delay chips [ns]
DELAY_CHIP_LIMITS_NS    = (5, 100)

# number of taps of the delay chips
DELAY_CHIP_TAPS         = 5

# the default delay chip max delay [ns]
DEFAULT_DELAY_CHIP_NS      = mcfd16_profile.DEFAULT_DELAY_CHIP_NS

CONV_TABLE_COINCIDENCE_NS = {
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

CONV_TABLE_DEADTIME_NS = {
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

CONV_TABLE_GATEGEN_NS = {
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

CONV_TABLE_WIDTH_NS = {
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

class Polarity(object):
    negative = 1
    positive = 0

    @staticmethod
    def switch(pol):
        if pol == Polarity.positive:
            return Polarity.negative
        return Polarity.positive

class DiscriminatorMode(object):
    le  = 0 # Leading Edge
    cfd = 1 # Constant Fraction

cg_helper = util.ChannelGroupHelper(NUM_CHANNELS, NUM_GROUPS)

# ==========  Device ========== 
class MCFD16(DeviceBase):

    trigger_pattern_changed = pyqtSignal(int, int)  # trigger index, pattern value
    pair_pattern_changed    = pyqtSignal(int, int)  # pattern index, pattern value
    delay_chip_ns_changed   = pyqtSignal(int)

    def __init__(self, app_device, read_mode, write_mode, parent=None):
        super(MCFD16, self).__init__(app_device, read_mode, write_mode, parent)

        self.log = util.make_logging_source_adapter(__name__, self)

        self.parameter_changed.connect(self._on_parameter_changed)

    def get_delay_chip_ns(self):
        return self.get_extension('delay_chip_ns')

    def set_delay_chip_ns(self, value):
        if self.get_delay_chip_ns() != value:
            self.set_extension('delay_chip_ns', value)
            self.delay_chip_ns_changed.emit(value)

    def get_effective_delay(self, group_or_common):
        if group_or_common == 'common':
            reg = 'delay_common'
        else:
            reg = 'delay_group%d' % group_or_common

        ret = future.Future()

        @set_result_on(ret)
        def done(f):
            return self.get_delay_chip_ns() / DELAY_CHIP_TAPS * (int(f) + 1)

        self.get_parameter(reg).add_done_callback(done)

        return ret

    def get_effective_threshold_mV(self, channel_idx_or_common):
        """Returns the effective threshold in mV for the given channel.
        The parameter channel_idx_or_common must be a numeric channel idx or
        the string 'common'.
        """
        if channel_idx_or_common == 'common':
            gain_param      = 'gain_common'
            threshold_param = 'threshold_common'
        else:
            gain_param      = 'gain_group%d' % cg_helper.channel_to_group(channel_idx_or_common)
            threshold_param = 'threshold_channel%d' % channel_idx_or_common

        ret         = future.Future()
        f_gain      = self.get_parameter(gain_param)
        f_thresh    = self.get_parameter(threshold_param)

        @set_result_on(ret)
        def done(f):
            gain                = int(f_gain)
            threshold           = int(f_thresh)
            max_threshold_mv    = MAX_THRESHOLD_BY_GAIN[gain]
            threshold_step_mv   = max_threshold_mv / 255
            threshold_mv        = threshold_step_mv * threshold

            return threshold_mv

        future.all_done(f_gain, f_thresh).add_done_callback(done)

        return ret

    def get_trigger_pattern(self, idx):
        f_high = self.get_parameter('trigger_pattern%d_high' % idx)
        f_low  = self.get_parameter('trigger_pattern%d_low' % idx)
        ret    = future.Future()

        @set_result_on(ret)
        def done(f):
            return ((int(f_high) << 8) | int(f_low))

        future.all_done(f_high, f_low).add_done_callback(done)

        return ret

    def set_trigger_pattern(self, idx, pattern):
        high   = (pattern & 0xFF00) >> 8
        low    = pattern & 0x00FF

        f_high = self.set_parameter('trigger_pattern%d_high' % idx, high)
        f_low  = self.set_parameter('trigger_pattern%d_low' % idx, low)

        return future.all_done(f_high, f_low)

    def get_pair_pattern(self, idx):
        f_high = self.get_parameter('pair_pattern%d_high' % idx)
        f_low  = self.get_parameter('pair_pattern%d_low'  % idx)
        ret    = future.Future()

        @set_result_on(ret)
        def done(f):
            return ((int(f_high) << 8) | int(f_low))

        future.all_done(f_high, f_low).add_done_callback(done)

        return ret

    def set_pair_pattern(self, idx, pattern):
        high = (pattern & 0xFF00) >> 8
        low  = pattern & 0x00FF

        f_high = self.set_parameter('pair_pattern%d_high' % idx, high)
        f_low  = self.set_parameter('pair_pattern%d_low'  % idx, low)

        return future.all_done(f_high, f_low)

    def _on_parameter_changed(self, address, value):
        pp = self.profile[address]
        if pp is None:
            return

        if re.match(r'trigger_pattern\d_.+', pp.name):
            def done(f):
                self.trigger_pattern_changed.emit(pp.index, f.result())

            self.get_trigger_pattern(pp.index).add_done_callback(done)

        elif re.match(r'pair_pattern\d+_.+', pp.name):
            def done(f):
                self.pair_pattern_changed.emit(pp.index, f.result())

            self.get_pair_pattern(pp.index).add_done_callback(done)

    def apply_common_polarity(self):
        return self._apply_common_to_single(
                'polarity_common', 'polarity_group%d', NUM_GROUPS)

    def apply_common_gain(self):
        return self._apply_common_to_single(
                'gain_common', 'gain_group%d', NUM_GROUPS)

    def apply_common_delay(self):
        return self._apply_common_to_single(
                'delay_common', 'delay_group%d', NUM_GROUPS)

    def apply_common_fraction(self):
        return self._apply_common_to_single(
                'fraction_common', 'fraction_group%d', NUM_GROUPS)

    def apply_common_threshold(self):
        return self._apply_common_to_single(
                'threshold_common', 'threshold_channel%d', NUM_CHANNELS)

    def apply_common_width(self):
        return self._apply_common_to_single(
                'width_common', 'width_group%d', NUM_GROUPS)

    def apply_common_deadtime(self):
        return self._apply_common_to_single(
                'deadtime_common', 'deadtime_group%d', NUM_GROUPS)

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

# ==========  GUI ========== 
dynamic_label_style = "QLabel { background-color: lightgrey; }"

class MCFD16Widget(DeviceWidgetBase):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(MCFD16Widget, self).__init__(device, display_mode, write_mode, parent)

        self.tab_widget.addTab(
                MCFD16ControlsWidget(device, display_mode, write_mode, self),
                "Preamp / CFD")

        self.tab_widget.addTab(
                MCFD16SetupWidget(device, display_mode, write_mode, self),
                "Trigger / Coincidence Setup")

    def get_parameter_bindings(self):
        tb  = self.tab_widget
        gen = (tb.widget(i).get_parameter_bindings() for i in range(tb.count()))
        return itertools.chain(*gen)

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

        for i in range(NUM_GROUPS):
            cb = QtGui.QCheckBox()
            r  = cg_helper.group_channel_range(NUM_GROUPS-i-1)
            l  = QtGui.QLabel("%d\n%d" % (r[1], r[0]))
            f  = l.font()
            f.setPointSize(8)
            l.setFont(f)

            self.checkboxes.append(cb)

            layout.addWidget(cb, 0, i+1, 1, 1, Qt.AlignCenter)
            layout.addWidget(l,  1, i+1, 1, 1, Qt.AlignCenter)

        self.result_label = make_dynamic_label(initial_value="0", longest_value=str(2**NUM_GROUPS-1))

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

class BitPatternBinding(pb.AbstractParameterBinding):
    def __init__(self, **kwargs):
        super(BitPatternBinding, self).__init__(**kwargs)
        self.target.value_changed.connect(self._write_value)

        if 'label' in kwargs:
            self.label = weakref.ref(kwargs['label'])
        else:
            self.label = None

    def _update(self, rf):
        with util.block_signals(self.target):
            self.target.set_value(int(rf))

        tt = self._get_tooltip(rf)

        if isinstance(self.target, QtGui.QWidget):
            self.target.setToolTip(tt)
            self.target.setStatusTip(tt)
        elif isinstance(self.target, BitPatternHelper):
            for cb in self.target.checkboxes:
                cb.setToolTip(tt)
                cb.setStatusTip(tt)

        if self.label and self.label():
            self.label().setText(str(int(rf)))

class TogglePolarityBinding(pb.DefaultParameterBinding):
    def __init__(self, **kwargs):
        super(TogglePolarityBinding, self).__init__(**kwargs)

        self._icons = kwargs['icons']
        self._polarity = Polarity.positive
        self.target.clicked.connect(self._toggle_polarity)

    def _update(self, rf):
        super(TogglePolarityBinding, self)._update(rf)
        self._polarity = int(rf)
        self.target.setIcon(self._icons[self._polarity])

    def _toggle_polarity(self):
        self._write_value(Polarity.switch(self._polarity))

class PreampPage(QtGui.QGroupBox):
    polarity_button_size = QtCore.QSize(20, 20)

    def __init__(self, device, display_mode, write_mode, parent=None):
        super(PreampPage, self).__init__("Preamp", parent)
        self.device  = device

        self.polarity_icons = {
                Polarity.positive: QtGui.QIcon(QtGui.QPixmap(":/polarity-positive.png").scaled(
                    PreampPage.polarity_button_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)),

                Polarity.negative: QtGui.QIcon(QtGui.QPixmap(":/polarity-negative.png").scaled(
                    PreampPage.polarity_button_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                }

        self.bindings = list()

        self.pol_common = QtGui.QPushButton()
        self.pol_common.setMaximumSize(PreampPage.polarity_button_size)
        self.bindings.append(TogglePolarityBinding(
            device=device, profile=device.profile['polarity_common'],
            target=self.pol_common, display_mode=display_mode, write_mode=write_mode,
            icons=self.polarity_icons))

        pol_common_layout = util.make_apply_common_button_layout(
                self.pol_common, "Apply to groups", self._apply_common_polarity)[0]

        self.pol_inputs = list()

        def make_gain_combo():
            ret = QtGui.QComboBox()
            for rc_value, gain in sorted(GAIN_FACTORS.iteritems()):
                ret.addItem(str(gain), rc_value)
            return ret

        self.gain_common = make_gain_combo()
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['gain_common'],
            target=self.gain_common, display_mode=display_mode, write_mode=write_mode))
        gain_common_layout = util.make_apply_common_button_layout(
                self.gain_common, "Apply to groups", self._apply_common_gain)[0]

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        offset = 0
        layout.addWidget(QtGui.QLabel("Common"),    offset, 0, 1, 1, Qt.AlignRight)
        layout.addLayout(pol_common_layout,         offset, 1, 1, 1, Qt.AlignCenter)
        layout.addLayout(gain_common_layout,        offset, 2)

        offset += 1
        layout.addWidget(make_title_label("Group"),    offset, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Polarity"), offset, 1)
        layout.addWidget(make_title_label("Gain"),     offset, 2, 1, 1, Qt.AlignCenter)

        self.gain_inputs = list()

        for i in range(NUM_GROUPS):
            offset      = layout.rowCount()
            group_range = cg_helper.group_channel_range(i)
            group_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1])) 

            pol_button  = QtGui.QPushButton()
            pol_button.setMaximumSize(PreampPage.polarity_button_size)
            self.bindings.append(TogglePolarityBinding(
                device=device, profile=device.profile['polarity_group%d' % i],
                target=pol_button, display_mode=display_mode, write_mode=write_mode,
                icons=self.polarity_icons))

            gain_combo = make_gain_combo()
            self.bindings.append(pb.factory.make_binding(
                device=device, profile=device.profile['gain_group%d' % i],
                target=gain_combo, display_mode=display_mode, write_mode=write_mode))

            self.pol_inputs.append(pol_button)
            self.gain_inputs.append(gain_combo)

            layout.addWidget(group_label,   offset, 0, 1, 1, Qt.AlignRight)
            layout.addWidget(pol_button,    offset, 1, 1, 1, Qt.AlignCenter)
            layout.addWidget(gain_combo,    offset, 2)

        layout.addWidget(hline(), layout.rowCount(), 0, 1, layout.columnCount()) # hline separator

        self.cb_bwl = QtGui.QCheckBox("BWL enable")
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['bwl_enable'],
            target=self.cb_bwl, display_mode=display_mode, write_mode=write_mode))

        layout.addWidget(self.cb_bwl, layout.rowCount(), 0, 1, layout.columnCount(), Qt.AlignRight)

    # GUI changes
    @future_progress_dialog()
    def _apply_common_polarity(self):
        return self.device.apply_common_polarity()

    @future_progress_dialog()
    def _apply_common_gain(self):
        return self.device.apply_common_gain()

def make_fraction_combo():
    ret = QtGui.QComboBox()

    for k in sorted(CFD_FRACTIONS.keys()):
        ret.addItem(CFD_FRACTIONS[k], k)

    return ret

class DiscriminatorPage(QtGui.QGroupBox):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(DiscriminatorPage, self).__init__("Discriminator", parent)
        self.device   = device
        self.bindings = list()

        # 1st row:  CFD/LE choice
        # 2nd row: common delay, fraction, threshold
        # 3rd row: column headers
        # following 16:  8 delays, 8 fractions, 16 thresholds
        # last row    : delay chip max delay

        def make_delay_combo():
            ret = QtGui.QComboBox()
            for i in range(device.profile['delay_common'].range[1]+1):
                ret.addItem("Tap %d" % i, i)

            return ret

        self.delay_common = make_delay_combo()
        self.delay_label_common = make_dynamic_label(longest_value='%d ns' % DELAY_CHIP_LIMITS_NS[1])
        self.delay_common_layout    = util.make_apply_common_button_layout(
                self.delay_common, "Apply to groups", self._apply_common_delay)[0]

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['delay_common'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.delay_common).add_update_callback(
                self._update_delay_label_cb, group='common'))

        self.fraction_common        = make_fraction_combo()
        self.fraction_common_layout = util.make_apply_common_button_layout(
                self.fraction_common, "Apply to groups", self._apply_common_fraction)[0]

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['fraction_common'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.fraction_common))

        self.threshold_common       = util.DelayedSpinBox()
        self.threshold_label_common = make_dynamic_label(longest_value='%.2f mV' % max(MAX_THRESHOLD_BY_GAIN.values()))
        self.threshold_common_layout= util.make_apply_common_button_layout(
                self.threshold_common, "Apply to channels", self._apply_common_threshold)[0]

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['threshold_common'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.threshold_common).add_update_callback(
                self._update_threshold_label_cb, channel='common'))

        self.delay_inputs       = list()
        self.delay_labels       = list()
        self.fraction_inputs    = list()
        self.threshold_inputs   = list()
        self.threshold_labels   = list()

        self.rb_mode_cfd = QtGui.QRadioButton("CFD")
        self.rb_mode_le  = QtGui.QRadioButton("LE")
        self.rbg_discriminator_mode = QtGui.QButtonGroup()
        self.rbg_discriminator_mode.addButton(self.rb_mode_cfd, DiscriminatorMode.cfd)
        self.rbg_discriminator_mode.addButton(self.rb_mode_le, DiscriminatorMode.le)

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['discriminator_mode'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.rbg_discriminator_mode))

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
        layout.addLayout(self.delay_common_layout,      offset, 1)
        layout.addWidget(self.delay_label_common,       offset, 2)
        layout.addLayout(self.fraction_common_layout,   offset, 3)
        layout.addWidget(QtGui.QLabel("Common"),        offset, 4)
        layout.addLayout(self.threshold_common_layout,  offset, 5)
        layout.addWidget(self.threshold_label_common,   offset, 6)

        offset = layout.rowCount()
        layout.addWidget(make_title_label("Group"),     offset, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Delay"),     offset, 1, 1, 1, Qt.AlignCenter)
        layout.addWidget(make_title_label("Fraction"),  offset, 3, 1, 1, Qt.AlignCenter)
        layout.addWidget(make_title_label("Chan"),      offset, 4, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Threshold"), offset, 5, 1, 1, Qt.AlignCenter)

        for i in range(NUM_CHANNELS):
            channels_per_group  = NUM_CHANNELS / NUM_GROUPS
            group               = int(i / channels_per_group)
            group_range         = cg_helper.group_channel_range(group)
            offset              = layout.rowCount()

            if i % channels_per_group == 0:
                group_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1])) 
                delay_input = util.DelayedSpinBox()
                delay_input.setPrefix("Tap ")
                delay_input = make_delay_combo()
                delay_label = make_dynamic_label(longest_value='%d ns' % DELAY_CHIP_LIMITS_NS[1])
                fraction_input = make_fraction_combo()

                self.bindings.append(pb.factory.make_binding(
                    device=device, profile=device.profile['delay_group%d' % group],
                    display_mode=display_mode, write_mode=write_mode,
                    target=delay_input).add_update_callback(
                        self._update_delay_label_cb, group=group))

                self.bindings.append(pb.factory.make_binding(
                    device=device, profile=device.profile['fraction_group%d' % group],
                    display_mode=display_mode, write_mode=write_mode,
                    target=fraction_input))

                self.delay_inputs.append(delay_input)
                self.delay_labels.append(delay_label)
                self.fraction_inputs.append(fraction_input)
                
                layout.addWidget(group_label,           offset, 0, 1, 1, Qt.AlignRight)
                layout.addWidget(delay_input,           offset, 1)
                layout.addWidget(delay_label,           offset, 2)
                layout.addWidget(fraction_input,        offset, 3)

            threshold_input = util.DelayedSpinBox()
            threshold_label = make_dynamic_label(longest_value='%.2f mV' % max(MAX_THRESHOLD_BY_GAIN.values()))

            self.bindings.append(pb.factory.make_binding(
                device=device, profile=device.profile['threshold_channel%d' % i],
                display_mode=display_mode, write_mode=write_mode,
                target=threshold_input).add_update_callback(
                    self._update_threshold_label_cb, channel=i))

            self.threshold_inputs.append(threshold_input)
            self.threshold_labels.append(threshold_label)

            layout.addWidget(QtGui.QLabel("%d" % i),    offset, 4, 1, 1, Qt.AlignRight)
            layout.addWidget(threshold_input,           offset, 5)
            layout.addWidget(threshold_label,           offset, 6)

        layout.addWidget(hline(), layout.rowCount(), 0, 1, 7) # hline separator

        # Delay chip
        self.delay_chip_input = make_spinbox(limits=DELAY_CHIP_LIMITS_NS, suffix=' ns', single_step=5,
                value = device.get_delay_chip_ns())
        self.delay_chip_input.valueChanged.connect(self._on_delay_chip_input_valueChanged)

        delay_chip_label = QtGui.QLabel("Delay chip")
        delay_chip_layout = QtGui.QHBoxLayout()
        delay_chip_layout.setSpacing(4)
        delay_chip_layout.addWidget(delay_chip_label)
        delay_chip_layout.addWidget(self.delay_chip_input)
        delay_chip_layout.addStretch(1)

        device.delay_chip_ns_changed.connect(self._on_device_delay_chip_ns_changed)

        layout.addLayout(delay_chip_layout, layout.rowCount(), 0, 1, 7)

        # Fast veto
        self.cb_fast_veto = QtGui.QCheckBox("Fast veto")
        layout.addWidget(self.cb_fast_veto, layout.rowCount(), 0, 1, 7)

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['fast_veto'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.cb_fast_veto))

        device.parameter_changed.connect(self._on_device_parameter_changed)

    # Device changes
    def _on_device_parameter_changed(self, address, value):
        pp = self.device.profile[address]
        if pp is None:
            return

        if pp.name == 'gain_common':
            self._update_threshold_label(self.threshold_label_common, 'common')
        elif re.match(r'gain_group\d', pp.name):
            channel_range = cg_helper.group_channel_range(pp.index)
            for chan in channel_range:
                self._update_threshold_label(self.threshold_labels[chan], chan)

    def _update_delay_label_cb(self, f, group):
        if group == 'common':
            label = self.delay_label_common
        else:
            label = self.delay_labels[group]

        self._update_delay_label(label, group)

    def _update_delay_label(self, label, group_or_common):
        def done(f):
            try:
                label.setText("%d ns" % int(f.result()))
                label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            except Exception:
                label.setText("N/A")
                label.setAlignment(Qt.AlignCenter)

        self.device.get_effective_delay(group_or_common).add_done_callback(done)

    def _update_threshold_label_cb(self, f, channel):
        if channel == 'common':
            label = self.threshold_label_common
        else:
            label = self.threshold_labels[channel]

        self._update_threshold_label(label, channel)

    def _update_threshold_label(self, label, channel_idx_or_common):
        def done(f):
            try:
                label.setText("%.2f mV" % f.result())
                label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            except Exception:
                label.setText("N/A")
                label.setAlignment(Qt.AlignCenter)

        self.device.get_effective_threshold_mV(channel_idx_or_common
                ).add_done_callback(done)

    def _on_device_delay_chip_ns_changed(self, value):
        spin = self.delay_chip_input
        with util.block_signals(spin):
            spin.setValue(value)
        self._update_delay_label(self.delay_label_common, 'common')
        for i in range(NUM_GROUPS):
            self._update_delay_label(self.delay_labels[i], i)

    # GUI changes
    def _on_delay_chip_input_valueChanged(self, value):
        self.device.set_delay_chip_ns(value)

    @future_progress_dialog()
    def _apply_common_delay(self):
        return self.device.apply_common_delay()

    @future_progress_dialog()
    def _apply_common_fraction(self):
        return self.device.apply_common_fraction()

    @future_progress_dialog()
    def _apply_common_threshold(self):
        return self.device.apply_common_threshold()

class WidthAndDeadtimePage(QtGui.QGroupBox):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(WidthAndDeadtimePage, self).__init__("Width/Dead time", parent=parent)

        self.device   = device
        self.bindings = list()

        # Columns: Group WidthInput WidthLabel DeadtimeInput DeadtimeLabel

        width_limits    = device.profile['width_common'].range.to_tuple()
        deadtime_limits = device.profile['deadtime_common'].range.to_tuple()

        width_ns_max    = CONV_TABLE_WIDTH_NS[width_limits[1]]
        deadtime_ns_max = CONV_TABLE_DEADTIME_NS[deadtime_limits[1]]

        self.width_common = util.DelayedSpinBox()
        self.width_common_layout = util.make_apply_common_button_layout(
                self.width_common, "Apply to groups", self._apply_common_width)[0]
        self.width_label_common = make_dynamic_label(longest_value="%d ns" % width_ns_max)

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['width_common'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.width_common).add_update_callback(
                self._update_width_label, group='common'))

        self.deadtime_common = make_spinbox(limits=deadtime_limits)
        self.deadtime_common_layout = util.make_apply_common_button_layout(
                self.deadtime_common, "Apply to groups", self._apply_common_deadtime)[0]
        self.deadtime_label_common = make_dynamic_label(longest_value="%d ns" % deadtime_ns_max)

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['deadtime_common'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.deadtime_common).add_update_callback(
                self._update_deadtime_label, group='common'))

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        offset = 0
        layout.addWidget(QtGui.QLabel("Common"),        offset, 0, 1, 1, Qt.AlignRight)
        layout.addLayout(self.width_common_layout,      offset, 1)
        layout.addWidget(self.width_label_common,       offset, 2)
        layout.addLayout(self.deadtime_common_layout,   offset, 3)
        layout.addWidget(self.deadtime_label_common,    offset, 4)

        offset += 1
        layout.addWidget(make_title_label("Group"),     offset, 0, 1, 1, Qt.AlignRight)
        layout.addWidget(make_title_label("Width"),     offset, 1, 1, 1, Qt.AlignCenter)
        layout.addWidget(make_title_label("Dead time"), offset, 3, 1, 1, Qt.AlignCenter)

        self.width_inputs = list()
        self.width_labels = list()
        self.deadtime_inputs = list()
        self.deadtime_labels = list()

        for i in range(NUM_GROUPS):
            offset      = layout.rowCount()
            group_range = cg_helper.group_channel_range(i)
            group_label = QtGui.QLabel("%d-%d" % (group_range[0], group_range[-1])) 

            width_input = util.DelayedSpinBox()
            width_label = make_dynamic_label(longest_value="%d ns" % width_ns_max)
            self.width_inputs.append(width_input)
            self.width_labels.append(width_label)

            self.bindings.append(pb.factory.make_binding(
                device=device, profile=device.profile['width_group%d' % i],
                display_mode=display_mode, write_mode=write_mode,
                target=width_input).add_update_callback(
                    self._update_width_label, group=i))

            deadtime_input = util.DelayedSpinBox()
            deadtime_label = make_dynamic_label(longest_value="%d ns" % deadtime_ns_max)
            self.deadtime_inputs.append(deadtime_input)
            self.deadtime_labels.append(deadtime_label)

            self.bindings.append(pb.factory.make_binding(
                device=device, profile=device.profile['deadtime_group%d' % i],
                display_mode=display_mode, write_mode=write_mode,
                target=deadtime_input).add_update_callback(
                    self._update_deadtime_label, group=i))

            layout.addWidget(group_label,       offset, 0, 1, 1, Qt.AlignRight)
            layout.addWidget(width_input,       offset, 1)
            layout.addWidget(width_label,       offset, 2)
            layout.addWidget(deadtime_input,    offset, 3)
            layout.addWidget(deadtime_label,    offset, 4)


    # Device changes
    def _update_width_label(self, f, group):
        if group == 'common':
            label = self.width_label_common
        else:
            label = self.width_labels[group]

        label.setText("%d ns" % CONV_TABLE_WIDTH_NS[int(f)])

    def _update_deadtime_label(self, f, group):
        if group == 'common':
            label = self.deadtime_label_common
        else:
            label = self.deadtime_labels[group]

        label.setText("%d ns" % CONV_TABLE_DEADTIME_NS[int(f)])

    # GUI changes
    @future_progress_dialog()
    def _apply_common_width(self):
        return self.device.apply_common_width()

    @future_progress_dialog()
    def _apply_common_deadtime(self):
        return self.device.apply_common_deadtime()

class MCFD16ControlsWidget(QtGui.QWidget):
    """Main MCFD16 controls: polarity, gain, delay, fraction, threshold, width, dead time."""
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(MCFD16ControlsWidget, self).__init__(parent)
        self.device  = device
        self.bindings = list()

        self.channel_mask_box       = ChannelMaskWidget(self)
        self.bindings.append(BitPatternBinding(
            device=device, profile=device.profile['channel_mask'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.channel_mask_box))

        self.preamp_page            = PreampPage(device, display_mode, write_mode, self)
        self.discriminator_page     = DiscriminatorPage(device, display_mode, write_mode, self)
        self.width_deadtime_page    = WidthAndDeadtimePage(device, display_mode, write_mode, self)

        # Channel mode
        mode_box = QtGui.QGroupBox("Channel Mode", self)
        mode_layout = QtGui.QGridLayout(mode_box)
        mode_layout.setContentsMargins(2, 2, 2, 2)
        self.rb_mode_single = QtGui.QRadioButton("Individual")
        self.rb_mode_common = QtGui.QRadioButton("Common")
        self.rb_mode_common.setEnabled(False)

        self.rbg_mode = QtGui.QButtonGroup()
        self.rbg_mode.addButton(self.rb_mode_single, 1)
        self.rbg_mode.addButton(self.rb_mode_common, 0)
        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['single_channel_mode'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.rbg_mode))

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

    def get_parameter_bindings(self):
        return itertools.chain(
                self.bindings,
                self.preamp_page.bindings,
                self.discriminator_page.bindings,
                self.width_deadtime_page.bindings)
                
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

class CoincidenceTimeSpinBoxBinding(pb.DefaultParameterBinding):
    # This needs special handling as the normal range is (3, 136) but
    # additionally 0 can be set to enable overlap coincidence. To make this
    # work with a spinbox the range is set to (2, 136) with the value 2
    # being replaced by the `special value text' "overlap". When handling
    # the valueChanged signal this has to be taken into account!

    def __init__(self, **kwargs):
        super(CoincidenceTimeSpinBoxBinding, self).__init__(**kwargs)

        with util.block_signals(self.target):
            self.target.setMinimum(2)
            self.target.setMaximum(self.profile.range[1])
            self.target.setSpecialValueText("overlap")
        self.target.delayed_valueChanged.connect(self._on_value_changed)

    def _on_value_changed(self, value):
        if value == self.target.minimum():
            value = 0

        self._write_value(value)

    def _update(self, rf):
        super(CoincidenceTimeSpinBoxBinding, self)._update(rf)
        value = max(int(rf), self.target.minimum())

        with util.block_signals(self.target):
            self.target.setValue(value)

class MultiByteIndexedSignalSlotBinding(object):
    """Usable for trigger_pattern and pair_pattern parameters."""
    def __init__(self, device, getter, setter, signal, index, target, label=None):

        getattr(device, signal).connect(self._update)
        target.value_changed.connect(self._write_value)

        self.device = weakref.ref(device)
        self.getter = getter
        self.setter = setter
        self.signal = signal
        self.index  = index
        self.target = target
        self.label  = weakref.ref(label) if label is not None else None

    def populate(self):
        def done(f):
            self.target.set_value(f.result())
            if self.label and self.label():
                self.label().setText(str(int(f.result())))

        getattr(self.device(), self.getter)(self.index).add_done_callback(done)

    def _update(self, idx, value):
        if idx != self.index:
            return

        with util.block_signals(self.target):
            self.target.set_value(value)

        if self.label and self.label():
            self.label().setText(str(value))

    def _write_value(self, value):
        getattr(self.device(), self.setter)(self.index, value)

class TriggerSetupWidget(QtGui.QWidget):
    """MCFD16 trigger setup widget"""
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(TriggerSetupWidget, self).__init__(parent)

        self.device = device
        self.bindings = list()

        layout = QtGui.QGridLayout(self)
        layout.setHorizontalSpacing(3)
        layout.setVerticalSpacing(5)
        layout.setContentsMargins(4, 4, 4, 4)

        trigger_labels  = ['OR all', 'Mult', 'PA', 'Mon0', 'Mon1', 'OR1', 'OR0', 'Veto', 'GG']
        trigger_names   = ['T0', 'T1', 'T2']
        self.trigger_checkboxes = [[] for i in range(len(trigger_names))]

        row_offset = 0
        col        = 7
        coinc_layout = QtGui.QHBoxLayout()
        coinc_layout.addWidget(QtGui.QLabel("Coincidence time:"))
        self.spin_coincidence_time = util.DelayedSpinBox()
        coinc_layout.addWidget(self.spin_coincidence_time)
        coincidence_value_max = CONV_TABLE_COINCIDENCE_NS[device.profile['coincidence_time'].range[1]]
        self.label_coincidence_time = make_dynamic_label(longest_value="%d ns" % coincidence_value_max)
        coinc_layout.addWidget(self.label_coincidence_time)
        layout.addLayout(coinc_layout, row_offset, col, Qt.AlignLeft)

        self.bindings.append(CoincidenceTimeSpinBoxBinding(
            device=device, profile=device.profile['coincidence_time'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.spin_coincidence_time).add_update_callback(
                self._update_coincidence_label))

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
            self.trigger_source_helpers.append(helper)

            label = vlabel.VerticalLabel("0", forceWidth=True)
            label.setStyleSheet(dynamic_label_style)
            layout.addWidget(label, label_row, i+1)
            self.trigger_source_labels.append(label)

            self.bindings.append(BitPatternBinding(
                device=device, profile=device.profile['trigger%d' % i],
                display_mode=display_mode, write_mode=write_mode,
                target=helper, label=label))


        # Set the label column to a fixed minimum height to work around a
        # problem with vlabel.VerticalLabel which does not honor setFixedSize() at
        # all and thus resizes depending on it's contents which causes ugly
        # re-layouts.
        layout.setRowMinimumHeight(label_row, 24)

        # Spacer between T2 and GG
        layout.addItem(QtGui.QSpacerItem(5, 1),
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
        self.gg_source_label  = vlabel.VerticalLabel("0")
        self.gg_source_label.setStyleSheet(dynamic_label_style)
        layout.addWidget(self.gg_source_label, label_row, gg_col)

        self.bindings.append(BitPatternBinding(
            device=device, profile=device.profile['gg_sources'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.gg_source_helper, label=self.gg_source_label))

        # Spacer between GG and the right side widgets
        layout.addItem(QtGui.QSpacerItem(15, 1),
                0, 6, layout.rowCount(), 1)

        # OR all label
        col = 7
        row = 2
        layout.addWidget(QtGui.QLabel("OR all channels"), row, col)

        # Multiplicity
        self.spin_mult_lo  = util.DelayedSpinBox()
        self.spin_mult_hi  = util.DelayedSpinBox()

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['multiplicity_lo'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.spin_mult_lo))

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['multiplicity_hi'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.spin_mult_hi))

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
            combo.addItems([("Channel %d" % i) for i in range(NUM_CHANNELS)])
            return combo

        # Monitor 0
        label = QtGui.QLabel("TM0:")
        sz    = label.sizeHint()
        label.setFixedSize(sz)
        combo = make_monitor_combo()
        mon_layout = QtGui.QHBoxLayout()
        mon_layout.setContentsMargins(0, 0, 0, 0)
        mon_layout.addWidget(label)
        mon_layout.addWidget(combo)
        mon_layout.addStretch(1)

        self.monitor_inputs = list()
        self.monitor_inputs.append(combo)

        row += 1
        layout.addLayout(mon_layout, row, col)

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['monitor0'],
            display_mode=display_mode, write_mode=write_mode,
            target=combo))

        # Monitor 1
        label = QtGui.QLabel("TM1:")
        label.setFixedSize(sz)
        combo = make_monitor_combo()
        mon_layout = QtGui.QHBoxLayout()
        mon_layout.setContentsMargins(0, 0, 0, 0)
        mon_layout.addWidget(label)
        mon_layout.addWidget(combo)
        mon_layout.addStretch(1)

        self.monitor_inputs.append(combo)

        row += 1
        layout.addLayout(mon_layout, row, col)

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['monitor1'],
            display_mode=display_mode, write_mode=write_mode,
            target=combo))

        # Trigger Pattern 1
        self.trigger_pattern1 = BitPatternWidget("TP1:")
        self.trigger_pattern1.setToolTip("trigger_pattern1_low, trigger_pattern1_high")
        self.trigger_pattern1.setStatusTip(self.trigger_pattern1.toolTip())
        self.trigger_pattern1.title_label.setFixedSize(sz)
        row += 1
        layout.addWidget(self.trigger_pattern1, row, col)

        self.bindings.append(MultiByteIndexedSignalSlotBinding(
            device=device,
            getter='get_trigger_pattern',
            setter='set_trigger_pattern',
            signal='trigger_pattern_changed',
            index=1,
            target=self.trigger_pattern1))

        # Trigger Pattern 0
        self.trigger_pattern0 = BitPatternWidget("TP0:")
        self.trigger_pattern0.setToolTip("trigger_pattern0_low, trigger_pattern0_high")
        self.trigger_pattern0.setStatusTip(self.trigger_pattern0.toolTip())
        self.trigger_pattern0.title_label.setFixedSize(sz)
        row += 1
        layout.addWidget(self.trigger_pattern0, row, col)

        self.bindings.append(MultiByteIndexedSignalSlotBinding(
            device=device,
            getter='get_trigger_pattern',
            setter='set_trigger_pattern',
            signal='trigger_pattern_changed',
            index=0,
            target=self.trigger_pattern0))

        # Veto
        row += 1
        layout.addWidget(QtGui.QLabel("Veto"), row, col)

        # GG leading edge delay
        self.spin_gg_le_delay  = util.DelayedSpinBox()
        self.label_gg_le_delay = make_dynamic_label(
                longest_value="%d ns" % CONV_TABLE_GATEGEN_NS[self.spin_gg_le_delay.maximum()])

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['gg_leading_edge_delay'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.spin_gg_le_delay).add_update_callback(
                self._update_label_gg_le_delay))

        # GG trailing edge delay
        self.spin_gg_te_delay  = util.DelayedSpinBox()
        self.label_gg_te_delay = make_dynamic_label(
                longest_value="%d ns" % CONV_TABLE_GATEGEN_NS[self.spin_gg_te_delay.maximum()])

        self.bindings.append(pb.factory.make_binding(
            device=device, profile=device.profile['gg_trailing_edge_delay'],
            display_mode=display_mode, write_mode=write_mode,
            target=self.spin_gg_te_delay).add_update_callback(
                self._update_label_gg_te_delay))

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

    def _update_coincidence_label(self, f):
        value = int(f)
        if value < self.spin_coincidence_time.minimum():
            text = str()
        else:
            text = '%d ns' % CONV_TABLE_COINCIDENCE_NS[value]

        self.label_coincidence_time.setText(text)

    def _update_label_gg_le_delay(self, rf):
        self.label_gg_le_delay.setText("%d ns" % CONV_TABLE_GATEGEN_NS[int(rf.result())])

    def _update_label_gg_te_delay(self, rf):
        self.label_gg_te_delay.setText("%d ns" % CONV_TABLE_GATEGEN_NS[int(rf.result())])

    def get_parameter_bindings(self):
        return self.bindings

class PairCoincidenceSetupWidget(QtGui.QWidget):
    """Pair coincidence matrix display."""

    # Displays the lower right part of the pair coincidence matrix. Rows 0-14
    # correspond to pair coincidence registers 1-15 (register 0 is unused!).
    # The first row contains one checkbox (pair(0, 1)). Each consecutive row
    # contains one more checkbox, up to 15 in the last row.

    def __init__(self, device, display_mode, write_mode, parent=None):
        super(PairCoincidenceSetupWidget, self).__init__(parent)

        self.device = device
        self.bindings = list()

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

        for i, items in enumerate(zip(self.pattern_helpers, self.pattern_labels)):
            helper, label = items
            self.bindings.append(MultiByteIndexedSignalSlotBinding(
                device=device,
                getter='get_pair_pattern',
                setter='set_pair_pattern',
                signal='pair_pattern_changed',
                index=i+1,
                target=helper,
                label=label))

            for cb in helper.checkboxes:
                cb.setToolTip("pair_pattern%d_low, pair_pattern%d_high" % (i+1, i+1))
                cb.setStatusTip(cb.toolTip())

    def get_parameter_bindings(self):
        return self.bindings

class MCFD16SetupWidget(QtGui.QWidget):
    def __init__(self, device, display_mode, write_mode, parent=None):
        super(MCFD16SetupWidget, self).__init__(parent)

        self.trigger_widget     = TriggerSetupWidget(
                device, display_mode, write_mode, self)

        self.coincidence_widget = PairCoincidenceSetupWidget(
                device, display_mode, write_mode, self)

        gbs = list()

        gb = QtGui.QGroupBox("Trigger setup")
        gb_layout = QtGui.QHBoxLayout(gb)
        gb_layout.setContentsMargins(0, 0, 0, 0)
        gb_layout.addWidget(self.trigger_widget)
        gbs.append(gb)

        gb = QtGui.QGroupBox("Pair coincidence")
        gb_layout = QtGui.QHBoxLayout(gb)
        gb_layout.setContentsMargins(0, 0, 0, 0)
        gb_layout.addWidget(self.coincidence_widget)
        gbs.append(gb)

        layout = QtGui.QGridLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # First row contains the group boxes
        for col, gb in enumerate(gbs):
            layout.addWidget(gb, 0, col)

        # row spacer
        layout.addItem(
                QtGui.QSpacerItem(0, 0, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding),
                layout.rowCount(), 0, 1, layout.columnCount())

        # column spacer
        layout.addItem(
                QtGui.QSpacerItem(0, 0, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding),
                0, layout.columnCount(), layout.rowCount(), 1)

        # stretch factor for spacer cells
        # => widgets stay top-left and won't grow
        layout.setColumnStretch(layout.columnCount() - 1, 1)
        layout.setRowStretch(layout.rowCount() - 1, 1)

    def get_parameter_bindings(self):
        return itertools.chain(
                self.trigger_widget.get_parameter_bindings(),
                self.coincidence_widget.get_parameter_bindings())

# ==========  Module ========== 
idc             = 26
device_class    = MCFD16
device_ui_class = MCFD16Widget
profile_dict    = mcfd16_profile.profile_dict
