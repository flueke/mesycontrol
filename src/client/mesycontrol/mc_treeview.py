#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtGui
from qt import pyqtSignal
from functools import partial

import config_tree_model as ctm
import config_tree_view as ctv
import hardware_tree_model as htm
import hardware_tree_view as htv
import util

def find_insertion_index(items, test_fun):
    prev_item = next((o for o in items if test_fun(o)), None)
    return items.index(prev_item) if prev_item is not None else len(items)

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

    def cfg_idx_for_hw_idx(self, hw_idx):
        hw_node = hw_idx.internalPointer()

        if isinstance(hw_node, htm.BusNode):
            mrc      = hw_node.parent.ref
            bus      = hw_node.bus_number
            cfg_node = self.cfg_model.find_node_by_ref(mrc).children[bus]
            return self.cfg_model.index_for_node(cfg_node)

        return self.cfg_model.index_for_ref(hw_node.ref)

    def hw_idx_for_cfg_idx(self, cfg_idx):
        cfg_node = cfg_idx.internalPointer()

        if isinstance(cfg_node, ctm.BusNode):
            mrc      = cfg_node.parent.ref
            bus      = cfg_node.bus_number
            hw_node = self.hw_model.find_node_by_ref(mrc).children[bus]
            return self.hw_model.index_for_node(hw_node)

        return self.hw_model.index_for_ref(cfg_node.ref)

    def _mrc_added(self, mrc):
        self.log.debug("_mrc_added: %s, url=%s, hw=%s, cfg=%s", mrc, mrc.url, mrc.hw, mrc.cfg)

        def print_mrc(mrc):
            self.log.debug("slot: %s, url=%s, hw=%s, cfg=%s", mrc, mrc.url, mrc.hw, mrc.cfg)

        mrc.config_model_set.connect(partial(print_mrc, mrc))
        mrc.hardware_model_set.connect(partial(print_mrc, mrc))

        cfg_node = self.cfg_model.find_node_by_ref(mrc)
        if cfg_node is None:
            cfg_node = ctm.MRCNode(mrc)
            for i in range(2):
                cfg_node.append_child(ctm.BusNode(i))

            # keep mrcs sorted by url
            idx = find_insertion_index(self.setup_node.children, lambda c: mrc.url < c.ref.url)
            self.cfg_model.add_node(cfg_node, self.setup_node, idx)

        hw_node = self.hw_model.find_node_by_ref(mrc)
        if hw_node is None:
            hw_node = htm.MRCNode(mrc)
            for i in range(2):
                hw_node.append_child(htm.BusNode(i))

            # keep mrcs sorted by url
            idx = find_insertion_index(self.hw_registry_node.children, lambda c: mrc.url < c.ref.url)
            self.hw_model.add_node(hw_node, self.hw_registry_node, idx)

        mrc.device_added.connect(self._device_added)
        mrc.device_removed.connect(self._device_removed)

    def _mrc_removed(self, mrc):
        self.log.debug("_mrc_removed: %s, url=%s, hw=%s, cfg=%s", mrc, mrc.url, mrc.hw, mrc.cfg)
        cfg_node = self.cfg_model.find_node_by_ref(mrc)
        self.cfg_model.remove_node(cfg_node)
        hw_node  = self.hw_model.find_node_by_ref(mrc)
        self.hw_model.remove_node(hw_node)

    def _device_added(self, device):
        self.log.debug("_device_added: %s", device)

        cfg_node = self.cfg_model.find_node_by_ref(device)
        if cfg_node is None:
            cfg_node    = ctm.DeviceNode(device)
            parent_node = self.cfg_model.find_node_by_ref(device.mrc).children[device.bus]
            row = find_insertion_index(parent_node.children, lambda c: device.address < c.ref.address)
            self.cfg_model.add_node(cfg_node, parent_node, row)

        hw_node = self.hw_model.find_node_by_ref(device)
        if hw_node is None:
            hw_node     = htm.DeviceNode(device)
            parent_node = self.hw_model.find_node_by_ref(device.mrc).children[device.bus]
            row = find_insertion_index(parent_node.children, lambda c: device.address < c.ref.address)
            self.hw_model.add_node(hw_node, parent_node, row)

    def _device_removed(self, device):
        self.log.debug("_device_removed: %s", device)
        cfg_node = self.cfg_model.find_node_by_ref(device)
        self.cfg_model.remove_node(cfg_node)
        hw_node  = self.hw_model.find_node_by_ref(device)
        self.hw_model.remove_node(hw_node)

class MCTreeView(QtGui.QWidget):
    hw_context_menu_requested   = pyqtSignal(object, object, object, object) #: node, idx, position, view
    cfg_context_menu_requested  = pyqtSignal(object, object, object, object) #: node, idx, position, view
    node_selected               = pyqtSignal(object, object, object) #: node, idx, view
    hw_node_selected            = pyqtSignal(object, object, object) #: node, idx, view
    cfg_node_selected           = pyqtSignal(object, object, object) #: node, idx, view

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

        self.cfg_view.expandAll()
        self.hw_view.expandAll()

        def on_splitter_moved(pos, index):
            print "splitter moved: pos=%d, index=%d" % (pos, index)

        splitter = QtGui.QSplitter()
        splitter.splitterMoved.connect(on_splitter_moved)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.hw_view)
        splitter.addWidget(self.cfg_view)

        layout = QtGui.QGridLayout(self)
        layout.addWidget(splitter, 0, 0)

    def _cfg_context_menu(self, pos):
        idx  = self.cfg_view.indexAt(pos)
        node = idx.internalPointer()
        self.cfg_context_menu_requested.emit(node, idx, pos, self.cfg_view)

    def _hw_context_menu(self, pos):
        idx  = self.hw_view.indexAt(pos)
        node = idx.internalPointer()
        self.hw_context_menu_requested.emit(node, idx, pos, self.hw_view)

    def cfg_idx_for_hw_idx(self, hw_idx):
        return self.director.cfg_idx_for_hw_idx(hw_idx)

    def hw_idx_for_cfg_idx(self, cfg_idx):
        return self.director.hw_idx_for_cfg_idx(cfg_idx)

    def _cfg_expanded(self, idx):
        if idx.internalPointer() is not self.cfg_model.root:
            self.hw_view.expand(self.hw_idx_for_cfg_idx(idx))

    def _cfg_collapsed(self, idx):
        self.hw_view.collapse(self.hw_idx_for_cfg_idx(idx))

    def _cfg_selection_current_changed(self, current, previous):
        self.hw_view.setCurrentIndex(self.hw_idx_for_cfg_idx(current))
        self.node_selected.emit(current.internalPointer(), current, self.cfg_view)
        self.cfg_node_selected.emit(current.internalPointer(), current, self.cfg_view)

    def _hw_expanded(self, idx):
        if idx.internalPointer() is not self.hw_model.root:
            self.cfg_view.expand(self.cfg_idx_for_hw_idx(idx))

    def _hw_collapsed(self, idx):
        self.cfg_view.collapse(self.cfg_idx_for_hw_idx(idx))

    def _hw_selection_current_changed(self, current, previous):
        self.cfg_view.setCurrentIndex(self.cfg_idx_for_hw_idx(current))
        self.node_selected.emit(current.internalPointer(), current, self.hw_view)
        self.hw_node_selected.emit(current.internalPointer(), current, self.hw_view)
