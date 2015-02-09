#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore

class HardwareTreeModel(QtCore.QAbstractItemModel):
    def __init__(self, context, parent=None):
        super(HardwareTreeModel, self).__init__(parent)
