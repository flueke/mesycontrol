#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import Qt
from qt import QtGui

class HardwareTreeView(QtGui.QTreeView):
    def __init__(self, parent=None):
        super(HardwareTreeView, self).__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setHeaderHidden(True)
        self.setTextElideMode(Qt.ElideNone)
        self.setRootIsDecorated(False)
