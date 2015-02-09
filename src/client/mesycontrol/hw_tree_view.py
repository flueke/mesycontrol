#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtGui

class HardwareTreeView(QtGui.QTreeView):
    def __init__(self, model, parent=None):
        super(HardwareTreeView, self).__init__(parent)
