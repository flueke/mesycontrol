#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from basic_tree_model import BasicTreeModel
from qt.QtCore import QModelIndex
from qt import Qt

class HardwareTreeModel(BasicTreeModel):
    def columnCount(self, parent=QModelIndex()):
        return 3

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return str(section)
        return None

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None
        return idx.internalPointer().data(idx.column(), role)
