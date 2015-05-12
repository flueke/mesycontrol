#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import Qt
from qt import QtGui
import config_tree_model as ctm

class ConfigTreeView(QtGui.QTreeView):
    def __init__(self, parent=None):
        super(ConfigTreeView, self).__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    def _context_menu(self, pos):
        idx  = self.indexAt(pos)
        node = idx.internalPointer()

        ret = QtGui.QMenu()
        
        if isinstance(node, ctm.SetupNode):
            def add_mrc():
                new_node = ctm.MRCNode()
                new_node.append_child(ctm.BusNode(0))
                new_node.append_child(ctm.BusNode(1))
                self.model().add_node(new_node, node, len(node.children))
                self.expandAll()

            ret.addAction("Add MRC").triggered.connect(add_mrc)
        elif isinstance(node, ctm.BusNode):
            def add_device():
                new_node = ctm.DeviceNode(bus=0, address=0)
                self.model().add_node(new_node, node, len(node.children))
            ret.addAction("Add Device").triggered.connect(add_device)

        elif isinstance(node, ctm.MRCNode):
            def remove_mrc():
                self.model().remove_node(node)
            ret.addAction("Remove MRC").triggered.connect(remove_mrc)

        elif isinstance(node, ctm.DeviceNode):
            def remove_device():
                self.model().remove_node(node)
            ret.addAction("Remove Device").triggered.connect(remove_device)

        ret.exec_(self.mapToGlobal(pos))
