#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

# Purpose: Create and test two tree views needed for mesycontrol: the hardware
# tree and the config tree. Both trees will be shown side by side and must be
# kept in sync (selections, item positions, react to item
# changes/adds/removes/...)

# Components:
# QAbstractItemModels: HardwareTreeModel, SetupTreeModel
# QTreeViews: HardwareTreeView, SetupTreeView
# TreeViewDirector: updates models
# TreeViewWidget: combines HardwareTreeView and SetupTreeView into one Widget

# Context Menu handling is external (MCTreeView)
# Selection Sync is external (MCTreeView)
# Sync of nodes is external (MCTreeView)
# how to handle changes to nodes?
# each specific node type knows when its' ref changes
# -> call a notify_changed method on the model

from qt import QtCore
from qt import QtGui
from qt import Qt

import config_tree_model as ctm
from config_tree_view import ConfigTreeView

import signal
import sys

def signal_handler(signum, frame):
    QtGui.QApplication.quit()

import app_model as am
import basic_model as bm
import hardware_model as hm
import config_model as cm

if __name__ == "__main__":
    QtGui.QApplication.setDesktopSettingsAware(False)
    app = QtGui.QApplication(sys.argv)
    app.setStyle(QtGui.QStyleFactory.create("Plastique"))

    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    signal.signal(signal.SIGINT, signal_handler)

    import pyqtgraph as pg
    import pyqtgraph.console

    console = pg.console.ConsoleWidget(namespace=locals())
    console.show()

    hw_registry     = bm.MRCRegistry()
    config_registry = cm.Setup()
    app_director    = am.Director(hw_registry, config_registry)

    ret = app.exec_()
    sys.exit(ret)
