#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

#HWTreeModel ConfigTreeModel
#HWTreeView  ConfigTreeView
#
#MesycontrolTreeView
# Side by side view of both of the above views + actions (save setup, load
# setup, save config, load config, remove device from config tree

from qt import QtGui

import config_tree_model
import config_tree_view
import hw_tree_model
import hw_tree_view

class MesycontrolTreeView(QtGui.QWidget):
    def __init__(self, context, parent=None):
        super(MesycontrolTreeView, self).__init__(parent)

        self.hw_model = hw_tree_model.HardwareTreeModel(context)
        self.hw_view  = hw_tree_view.HardwareTreeView(self.hw_model)

        self.config_model = config_tree_model.ConfigTreeModel(context)
        self.config_view  = config_tree_view.ConfigTreeView(self.config_model)

        splitter = QtGui.QSplitter()
        splitter.addWidget(self.hw_view)
        splitter.addWidget(self.config_view)

        layout = QtGui.QGridLayout(self)
        layout.addWidget(splitter, 0, 0)

if __name__ == "__main__":
    import sys
    import mock
    app = QtGui.QApplication(sys.argv)
    context = mock.Mock()
    v = MesycontrolTreeView(context)
    v.show()
    sys.exit(app.exec_())
