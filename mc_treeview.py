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

class AddDeviceDialog(QtGui.QDialog):
    def __init__(self, mrc, bus=None, parent=None):
        super(AddDeviceDialog, self).__init__(parent)
        self._result = (0, 0, 27)
        ok = QtGui.QPushButton("ok", self)
        ok.clicked.connect(self.accept)

    def result(self):
        return self._result

class MCTreeDirector(object):
    def __init__(self, app_director):
        self.log       = util.make_logging_source_adapter(__name__, self)

        self.cfg_model  = ctm.ConfigTreeModel()
        self.setup_node = ctm.SetupNode(app_director.registry, self.cfg_model.root)
        self.cfg_model.add_node(self.setup_node, self.cfg_model.root, 0)

        self.hw_registry_node = htm.RegistryNode(app_director.registry)
        self.hw_model  = htm.HardwareTreeModel()
        self.hw_model.add_node(self.hw_registry_node, self.hw_model.root, 0)

        for mrc in app_director.registry.get_mrcs():
            self._mrc_added(mrc)

        app_director.registry.mrc_added.connect(self._mrc_added)
        app_director.registry.mrc_removed.connect(self._mrc_removed)

    def _mrc_added(self, mrc):
        self.log.debug("_mrc_added: %s, url=%s, hw=%s, cfg=%s", mrc, mrc.url, mrc.hw, mrc.cfg)

        def print_mrc(mrc):
            self.log.debug("slot: %s, url=%s, hw=%s, cfg=%s", mrc, mrc.url, mrc.hw, mrc.cfg)

        mrc.config_model_set.connect(partial(print_mrc, mrc))
        mrc.hardware_model_set.connect(partial(print_mrc, mrc))

        cfg_node = self.cfg_model.root.find_node_by_ref(mrc)
        if cfg_node is None:
            cfg_node = ctm.MRCNode(mrc)
            for i in range(2):
                cfg_node.append_child(ctm.BusNode(i))
            self.cfg_model.add_node(cfg_node, self.setup_node, len(self.setup_node.children))

        hw_node = self.hw_model.root.find_node_by_ref(mrc)
        if hw_node is None:
            hw_node = htm.MRCNode(mrc)
            for i in range(2):
                hw_node.append_child(htm.BusNode(i))
            self.hw_model.add_node(hw_node, self.hw_registry_node, len(self.hw_registry_node.children))

        mrc.device_added.connect(self._device_added) # XXX: leftoff

    def _mrc_removed(self, mrc):
        self.log.debug("_mrc_removed: %s, url=%s, hw=%s, cfg=%s", mrc, mrc.url, mrc.hw, mrc.cfg)
        cfg_node = self.cfg_model.root.find_node_by_ref(mrc)
        self.cfg_model.remove_node(cfg_node)
        hw_node  = self.hw_model.root.find_node_by_ref(mrc)
        self.hw_model.remove_node(hw_node)

class MCTreeView(QtGui.QWidget):
    def __init__(self, app_director, parent=None):
        super(MCTreeView, self).__init__(parent)

        self.app_director = app_director
        self.director  = MCTreeDirector(app_director)

        self.cfg_model = self.director.cfg_model
        self.hw_model  = self.director.hw_model

        self.cfg_view  = ctv.ConfigTreeView()
        self.cfg_view.setModel(self.cfg_model)
        self.cfg_model.rowsInserted.connect(self.cfg_view.expandAll)
        self.cfg_model.rowsInserted.connect(partial(self.cfg_view.resizeColumnToContents, 0))
        self.cfg_view.customContextMenuRequested.connect(self._cfg_context_menu)
        self.cfg_view.expanded.connect(self._cfg_expanded)
        self.cfg_view.collapsed.connect(self._cfg_collapsed)
        self.cfg_view.selectionModel().currentChanged.connect(self._cfg_selection_current_changed)

        self.hw_view   = htv.HardwareTreeView()
        self.hw_view.setModel(self.hw_model)
        self.hw_model.rowsInserted.connect(self.hw_view.expandAll)
        self.hw_model.rowsInserted.connect(partial(self.hw_view.resizeColumnToContents, 0))
        self.hw_view.customContextMenuRequested.connect(self._hw_context_menu)
        self.hw_view.expanded.connect(self._hw_expanded)
        self.hw_view.collapsed.connect(self._hw_collapsed)
        self.hw_view.selectionModel().currentChanged.connect(self._hw_selection_current_changed)

        splitter = QtGui.QSplitter()
        splitter.addWidget(self.hw_view)
        splitter.addWidget(self.cfg_view)

        layout = QtGui.QGridLayout(self)
        layout.addWidget(splitter, 0, 0)

    def _cfg_context_menu(self, pos):
        idx  = self.cfg_view.indexAt(pos)
        node = idx.internalPointer()
        menu  = QtGui.QMenu()

        if isinstance(node, ctm.SetupNode):
            def add_mrc():
                url, ok = QtGui.QInputDialog.getText(self.cfg_view, "Enter MRC URL", "URL:")
                if not ok or len(url) == 0:
                    return
                try:
                    print self.app_director
                    print self.app_director.registry
                    print self.app_director.registry.cfg
                    self.app_director.registry.cfg.add_mrc(cm.MRC(url))
                except Exception as e:
                    #d = QtGui.QErrorMessage(self.cfg_view)
                    #d.showMessage(str(e))
                    #import traceback
                    #traceback.print_exc()
                    QtGui.QMessageBox.critical(self.cfg_view, "Error adding MRC", str(e))

            menu.addAction("Add MRC").triggered.connect(add_mrc)

        if isinstance(node, ctm.MRCNode):
            mrc = node.ref
            def remove_mrc():
                self.app_director.registry.cfg.remove_mrc(mrc.cfg)

            def add_device():
                dialog = AddDeviceDialog(mrc=mrc, parent=self.cfg_view)
                dialog.setModal(True)

                def dialog_accepted():
                    bus, address, idc = dialog.result()
                    device = cm.Device(bus, address, idc)
                    mrc.add_device(device)

                dialog.accepted.connect(dialog_accepted)
                dialog.show()

            menu.addAction("Add Device").triggered.connect(add_device)
            menu.addAction("Remove MRC").triggered.connect(remove_mrc)

        if isinstance(node, ctm.BusNode):
            pass

        if not menu.isEmpty():
            menu.exec_(self.cfg_view.mapToGlobal(pos))

    def _cfg_expanded(self, idx):
        cfg_node = idx.internalPointer()
        if cfg_node is not self.cfg_model.root:
            self.hw_view.expand(self.hw_model.index_for_ref(cfg_node.ref))

    def _cfg_collapsed(self, idx):
        self.hw_view.collapse(self.hw_model.index_for_ref(
            idx.internalPointer().ref))

    def _cfg_selection_current_changed(self, current, previous):
        print self, current.internalPointer()
        node = current.internalPointer()
        if isinstance(node, ctm.BusNode):
            mrc = node.parent.ref
            bus = node.bus_number
            hw_node = self.hw_model.find_node_by_ref(mrc).children[bus]
            hw_idx  = self.hw_model.index_for_node(hw_node)
        else:
            hw_idx = self.hw_model.index_for_ref(node.ref)
        self.hw_view.setCurrentIndex(hw_idx)

    def _hw_context_menu(self, pos):
        idx  = self.hw_view.indexAt(pos)
        node = idx.internalPointer()
        menu  = QtGui.QMenu()
        menu.addAction("Foobar")

        if not menu.isEmpty():
            menu.exec_(self.hw_view.mapToGlobal(pos))

    def _hw_expanded(self, idx):
        hw_node  = idx.internalPointer()
        if hw_node is not self.hw_model.root:
            self.cfg_view.expand(self.cfg_model.index_for_ref(hw_node.ref))

    def _hw_collapsed(self, idx):
        self.cfg_view.collapse(self.cfg_model.index_for_ref(
            idx.internalPointer().ref))

    def _hw_selection_current_changed(self, current, previous):
        print self, current.internalPointer()
        node = current.internalPointer()
        if isinstance(node, htm.BusNode):
            mrc = node.parent.ref
            bus = node.bus_number
            cfg_node = self.cfg_model.find_node_by_ref(mrc).children[bus]
            cfg_idx  = self.cfg_model.index_for_node(cfg_node)
        else:
            cfg_idx = self.cfg_model.index_for_ref(node.ref)
        self.cfg_view.setCurrentIndex(cfg_idx)

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

    import pyqtgraph as pg
    import pyqtgraph.console

    console = pg.console.ConsoleWidget(namespace=locals())
    console.show()

    sys.exit(app.exec_())
