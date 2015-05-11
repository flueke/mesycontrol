#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtGui
from qt import QtCore
import logging
from functools import partial

import app_model
import basic_model as bm
import config_model as cm
import config_tree_model as ctm
import config_tree_view as ctv
import hardware_tree_model as htm
import hardware_tree_view as htv
import util

class MCTreeDirector(object):
    def __init__(self, app_director):
        self.log       = util.make_logging_source_adapter(__name__, self)

        self.setup_node = ctm.SetupNode(app_director.cfg_registry)
        self.cfg_model  = ctm.ConfigTreeModel()
        self.cfg_model.add_node(self.setup_node, self.cfg_model.root, 0)

        self.hw_registry_node = htm.RegistryNode(app_director.hw_registry)
        self.hw_model  = htm.HardwareTreeModel()
        self.hw_model.add_node(self.hw_registry_node, self.hw_model.root, 0)

        for mrc in app_director.registry.get_mrcs():
            self._mrc_added(mrc)

        app_director.registry.mrc_added.connect(self._mrc_added)

    def _mrc_added(self, mrc):
        self.log.debug("_mrc_added: %s, url=%s, hw=%s, cfg=%s", mrc, mrc.url, mrc.hw, mrc.cfg)

        cfg_node = self.cfg_model.root.find_node_by_ref(mrc.cfg)
        if cfg_node is None:
            cfg_node = ctm.MRCNode(mrc.cfg)
            for i in range(2):
                cfg_node.append_child(ctm.BusNode(i))
            self.cfg_model.add_node(cfg_node, self.setup_node, len(self.setup_node.children))

        hw_node = self.hw_model.root.find_node_by_ref(mrc.hw)
        if hw_node is None:
            hw_node = htm.MRCNode(mrc.hw)
            for i in range(2):
                hw_node.append_child(htm.BusNode(i))
            self.hw_model.add_node(hw_node, self.hw_registry_node, len(self.hw_registry_node.children))

class MCTreeView(QtGui.QWidget):
    def __init__(self, app_director, parent=None):
        super(MCTreeView, self).__init__(parent)

        self.app_director = app_director
        self.director  = MCTreeDirector(app_director)

        self.cfg_view  = ctv.ConfigTreeView()
        self.cfg_view.setModel(self.director.cfg_model)
        self.director.cfg_model.rowsInserted.connect(self.cfg_view.expandAll)
        self.director.cfg_model.rowsInserted.connect(partial(self.cfg_view.resizeColumnToContents, 0))
        self.cfg_view.customContextMenuRequested.connect(self._cfg_context_menu)
        self.cfg_view.expanded.connect(self._cfg_expanded)
        self.cfg_view.collapsed.connect(self._cfg_collapsed)
        self.cfg_view.selectionModel().currentChanged.connect(self._cfg_selection_current_changed)

        self.hw_view   = htv.HardwareTreeView()
        self.hw_view.setModel(self.director.hw_model)
        self.director.hw_model.rowsInserted.connect(self.hw_view.expandAll)
        self.director.hw_model.rowsInserted.connect(partial(self.hw_view.resizeColumnToContents, 0))
        self.hw_view.customContextMenuRequested.connect(self._hw_context_menu)

        splitter = QtGui.QSplitter()
        splitter.addWidget(self.hw_view)
        splitter.addWidget(self.cfg_view)

        layout = QtGui.QGridLayout(self)
        layout.addWidget(splitter, 0, 0)

    def _cfg_context_menu(self, pos):
        idx  = self.cfg_view.indexAt(pos)
        node = idx.internalPointer()
        ret  = QtGui.QMenu()

        if isinstance(node, ctm.SetupNode):
            def add_mrc():
                url, ok = QtGui.QInputDialog.getText(self.cfg_view, "Enter MRC URL", "URL:")
                if not ok or len(url) == 0:
                    return
                try:
                    self.app_director.cfg_registry.add_mrc(cm.MRC(url))
                except Exception as e:
                    d = QtGui.QErrorMessage(self.cfg_view)
                    d.showMessage(str(e))

            ret.addAction("Add MRC").triggered.connect(add_mrc)

        ret.exec_(self.cfg_view.mapToGlobal(pos))

    def _cfg_expanded(self, idx):
        print idx.internalPointer()

    def _cfg_collapsed(self, idx):
        print idx.internalPointer()

    def _cfg_selection_current_changed(self, current, previous):
        print self, current.internalPointer()

    def _hw_context_menu(self, pos):
        idx  = self.hw_view.indexAt(pos)
        node = idx.internalPointer()
        ret  = QtGui.QMenu()
        ret.addAction("Foobar")

        ret.exec_(self.hw_view.mapToGlobal(pos))

import signal

def signal_handler(signum, frame):
    QtGui.QApplication.quit()

if __name__ == "__main__":
    import sys
    import mock

    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    app = QtGui.QApplication(sys.argv)

    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    signal.signal(signal.SIGINT, signal_handler)

    hw_registry  = bm.MRCRegistry()
    cfg_registry = cm.Setup()
    app_director = app_model.Director(hw_registry, cfg_registry)

    v = MCTreeView(app_director)
    v.show()

    cfg_registry.add_mrc(cm.MRC("foo"))

    import pyqtgraph as pg
    import pyqtgraph.console

    console = pg.console.ConsoleWidget(namespace=locals())
    console.show()

    sys.exit(app.exec_())
