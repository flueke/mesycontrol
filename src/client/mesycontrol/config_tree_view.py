#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtGui

class ConfigTreeView(QtGui.QTreeView):
    def __init__(self, model, parent=None):
        super(ConfigTreeView, self).__init__(parent)

