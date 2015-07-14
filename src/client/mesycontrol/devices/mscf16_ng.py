#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from .. qt import QtGui

from .. import device
from .. import util

import device_profile_mscf16

NUM_CHANNELS        = 16        # number of channels
NUM_GROUPS          =  4        # number of channel groups
GAIN_FACTOR         = 1.22      # gain step factor
GAIN_ADJUST_LIMITS  = (1, 100)  # limits of the hardware gain jumpers

cg_helper = util.ChannelGroupHelper(NUM_CHANNELS, NUM_GROUPS)

class MSCF16(device.Device):
    def __init__(self, app_device, read_mode, write_mode, parent=None):
        super(MSCF16, self).__init__(app_device, parent)
        self.log = util.make_logging_source_adapter(__name__, self)

class MSCF16Widget(QtGui.QWidget):
    def __init__(self, device, parent=None):
        super(MSCF16Widget, self).__init__(parent)

idc             = 20
device_class    = MSCF16
device_ui_class = MSCF16Widget
profile_dict    = device_profile_mscf16.profile_dict
