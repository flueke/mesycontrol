#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtGui
from qt import QtCore
import logging
from functools import partial
import collections

import app_model
import basic_model as bm
import config_model as cm
import config_tree_model as ctm
import config_tree_view as ctv
import hardware_tree_model as htm
import hardware_tree_view as htv
import util

class AddDeviceDialog(QtGui.QDialog):
    Result = collections.namedtuple("Result", "bus address idc")

    def __init__(self, mrc, bus=None, parent=None):
        super(AddDeviceDialog, self).__init__(parent)
        self._result = None

        self.bus_combo = QtGui.QComboBox()
        self.bus_combo.addItems([str(i) for i in range(2)])

        if bus is not None:
            self.bus_combo.setCurrentIndex(bus)
            self.bus_combo.setEnabled(False)

        self.address_combo = QtGui.QComboBox()
        self.address_combo.addItems([str(i) for i in range(16)])

        self.idc_input = QtGui.QLineEdit()
        self.idc_input.setValidator(QtGui.QIntValidator(1, 99))

        self.button_box = QtGui.QDialogButtonBox(
                QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)

        ok_button = self.button_box.button(QtGui.QDialogButtonBox.Ok)
        ok_button.setEnabled(False)

        def idc_text_changed():
            ok_button.setEnabled(self.idc_input.hasAcceptableInput())

        self.idc_input.textChanged.connect(idc_text_changed)

        def accept():
            self._result = AddDeviceDialog.Result(
                    self.bus_combo.currentIndex(),
                    self.address_combo.currentIndex(),
                    int(str(self.idc_input.text())))
            self.accept()

        self.button_box.accepted.connect(accept)
        self.button_box.rejected.connect(self.reject)

        layout = QtGui.QFormLayout(self)
        layout.addRow("Bus", self.bus_combo)
        layout.addRow("Address", self.address_combo)
        layout.addRow("IDC", self.idc_input)
        layout.addRow(self.button_box)

    def result(self):
        return self._result

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
                    self.app_director.registry.cfg.add_mrc(cm.MRC(url))
                except Exception as e:
                    QtGui.QMessageBox.critical(self.cfg_view, "Error adding MRC", str(e))

            menu.addAction("Add MRC").triggered.connect(add_mrc)

        if isinstance(node, ctm.MRCNode):
            mrc = node.ref
            def remove_mrc():
                self.app_director.registry.cfg.remove_mrc(mrc.cfg)

            def add_device():
                dialog = AddDeviceDialog(mrc=mrc, parent=self)
                dialog.setModal(True)

                def dialog_accepted():
                    bus, address, idc = dialog.result()
                    device = cm.Device(bus, address, idc)
                    mrc.cfg.add_device(device)

                dialog.accepted.connect(dialog_accepted)
                dialog.show()

            menu.addAction("Add Device").triggered.connect(add_device)
            menu.addAction("Remove MRC").triggered.connect(remove_mrc)

        if isinstance(node, ctm.BusNode):
            mrc = node.parent.ref
            bus = node.bus_number

            def add_device():
                dialog = AddDeviceDialog(mrc=mrc, bus=bus, parent=self)
                dialog.setModal(True)

                def dialog_accepted():
                    bus, address, idc = dialog.result()
                    device = cm.Device(bus, address, idc)
                    mrc.cfg.add_device(device)

                dialog.accepted.connect(dialog_accepted)
                dialog.show()

            menu.addAction("Add Device").triggered.connect(add_device)

        # FIXME: handle node.ref.cfg is None
        if isinstance(node, ctm.DeviceNode):
            def remove_device():
                mrc = node.ref.cfg.mrc
                mrc.remove_device(node.ref.cfg)

            menu.addAction("Remove Device").triggered.connect(remove_device)

        if not menu.isEmpty():
            menu.exec_(self.cfg_view.mapToGlobal(pos))

    def _hw_context_menu(self, pos):
        idx  = self.hw_view.indexAt(pos)
        node = idx.internalPointer()
        menu  = QtGui.QMenu()
        menu.addAction("Foobar")

        if not menu.isEmpty():
            menu.exec_(self.hw_view.mapToGlobal(pos))

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

    def _hw_expanded(self, idx):
        if idx.internalPointer() is not self.hw_model.root:
            self.cfg_view.expand(self.cfg_idx_for_hw_idx(idx))

    def _hw_collapsed(self, idx):
        self.cfg_view.collapse(self.cfg_idx_for_hw_idx(idx))

    def _hw_selection_current_changed(self, current, previous):
        self.cfg_view.setCurrentIndex(self.cfg_idx_for_hw_idx(current))

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

    mrc    = cm.MRC("bbb")
    mrc2   = cm.MRC("aaa")
    mrc3   = cm.MRC("ccc")
    cfg_registry.add_mrc(mrc)
    cfg_registry.add_mrc(mrc2)
    cfg_registry.add_mrc(mrc3)

    d1 = cm.Device(0, 0, 42)
    d2 = cm.Device(0, 1, 43)
    d3 = cm.Device(1, 15, 44)
    d4 = cm.Device(1, 14, 45)
    d5 = cm.Device(1, 0, 41)

    mrc.add_device(d1)
    mrc.add_device(d2)
    mrc.add_device(d3)
    mrc.add_device(d4)
    mrc.add_device(d5)

    import pyqtgraph as pg
    import pyqtgraph.console

    console = pg.console.ConsoleWidget(namespace=locals())
    #console.show()

    sys.exit(app.exec_())
