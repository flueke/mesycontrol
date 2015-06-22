#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
from qt import pyqtProperty
from qt import pyqtSignal
from qt import Qt
from qt import QtCore
from qt import QtGui

import config_tree_model as ctm
import hardware_tree_model as htm
import util

# TODO: context menu and display for virtual items

class ConfigTreeView(QtGui.QTreeView):
    def __init__(self, parent=None):
        super(ConfigTreeView, self).__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setHeaderHidden(True)
        self.setTextElideMode(Qt.ElideNone)
        self.setRootIsDecorated(False)
        self.setExpandsOnDoubleClick(False)

class HardwareTreeView(QtGui.QTreeView):
    def __init__(self, parent=None):
        super(HardwareTreeView, self).__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setHeaderHidden(True)
        self.setTextElideMode(Qt.ElideNone)
        self.setRootIsDecorated(False)
        self.setExpandsOnDoubleClick(False)

def find_insertion_index(items, test_fun):
    prev_item = next((o for o in items if test_fun(o)), None)
    return items.index(prev_item) if prev_item is not None else len(items)

class MCTreeDirector(object):
    def __init__(self, app_registry, device_registry, find_data_file, linked_mode_on=False):
        self.log       = util.make_logging_source_adapter(__name__, self)

        self.app_registry = app_registry
        self.app_registry.mrc_added.connect(self._mrc_added)
        self.app_registry.mrc_about_to_be_removed.connect(self._mrc_about_to_be_removed)

        self.cfg_model = ctm.ConfigTreeModel(device_registry=device_registry)

        self.hw_model  = htm.HardwareTreeModel(device_registry=device_registry,
                find_data_file=find_data_file)

        self._linked_mode = linked_mode_on
        self._populate_models()

    def set_linked_mode(self, on_off):
        if self._linked_mode == on_off:
            return

        self._linked_mode = on_off
        self.cfg_model.clear()
        self.hw_model.clear()

        # Disconnect app_model signals before repopulating the model to avoid
        # duplicating signal/slot connections. Quite ugly :(
        for mrc in self.app_registry:

            mrc.device_added.disconnect(self._device_added)
            mrc.device_about_to_be_removed.disconnect(self._device_about_to_be_removed)
            mrc.hardware_set.disconnect(self._mrc_hardware_set)
            mrc.config_set.disconnect(self._mrc_config_set)

            for device in mrc:
                device.hardware_set.disconnect(self._device_hardware_set)
                device.config_set.disconnect(self._device_config_set)

        self._populate_models()

    def get_linked_mode(self):
        return self._linked_mode

    linked_mode = property(get_linked_mode, set_linked_mode)

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

    def _populate_models(self):
        self.setup_node = ctm.SetupNode(self.app_registry)
        self.cfg_model.add_node(self.setup_node, self.cfg_model.root, 0)

        self.hw_registry_node = htm.RegistryNode(self.app_registry)
        self.hw_model.add_node(self.hw_registry_node, self.hw_model.root, 0)

        for mrc in self.app_registry.get_mrcs():
            self._mrc_added(mrc)

    ########## MRC ########## 
    def _add_hw_mrc_node(self, mrc):
        if self.hw_model.find_node_by_ref(mrc) is not None:
            raise RuntimeError("Node exists")

        node = htm.MRCNode(mrc)
        for i in range(2):
            node.append_child(htm.BusNode(i))

        # keep mrcs sorted by url
        idx = find_insertion_index(self.hw_registry_node.children, lambda c: mrc.url < c.ref.url)
        self.hw_model.add_node(node, self.hw_registry_node, idx)

    def _add_cfg_mrc_node(self, mrc):
        if self.cfg_model.find_node_by_ref(mrc) is not None:
            raise RuntimeError("Node exists")

        node = ctm.MRCNode(mrc)
        for i in range(2):
            node.append_child(ctm.BusNode(i))

        # keep mrcs sorted by url
        idx = find_insertion_index(self.setup_node.children, lambda c: mrc.url < c.ref.url)
        self.cfg_model.add_node(node, self.setup_node, idx)

    def _mrc_added(self, mrc):
        self.log.debug("_mrc_added: %s, url=%s, hw=%s, cfg=%s", mrc, mrc.url, mrc.hw, mrc.cfg)

        cfg_node = self.cfg_model.find_node_by_ref(mrc)
        if cfg_node is None and (self.linked_mode or mrc.cfg is not None):
            self._add_cfg_mrc_node(mrc)

        hw_node = self.hw_model.find_node_by_ref(mrc)
        if hw_node is None and (self.linked_mode or mrc.hw is not None):
            self._add_hw_mrc_node(mrc)

        for device in mrc:
            self._device_added(device)

        mrc.device_added.connect(self._device_added)
        mrc.device_about_to_be_removed.connect(self._device_about_to_be_removed)
        mrc.hardware_set.connect(self._mrc_hardware_set)
        mrc.config_set.connect(self._mrc_config_set)

    def _mrc_hardware_set(self, mrc, old_hw, new_hw):
        self.log.debug("_mrc_hardware_set: %s, %s, %s", mrc, old_hw, new_hw)

        node = self.hw_model.find_node_by_ref(mrc)

        if new_hw is None and not self.linked_mode:
            assert node is not None
            self.hw_model.remove_node(node)
        elif new_hw is not None and node is None:
            self._add_hw_mrc_node(mrc)

    def _mrc_config_set(self, mrc, old_cfg, new_cfg):
        self.log.debug("mrc_config_set: %s, %s, %s", mrc, old_cfg, new_cfg)

        node = self.cfg_model.find_node_by_ref(mrc)

        if new_cfg is None and not self.linked_mode:
            assert node is not None
            self.cfg_model.remove_node(node)
        elif new_cfg is not None and node is None:
            self._add_cfg_mrc_node(mrc)

    def _mrc_about_to_be_removed(self, mrc):
        self.log.debug("_mrc_about_to_be_removed: %s, url=%s, hw=%s, cfg=%s", mrc, mrc.url, mrc.hw, mrc.cfg)

        cfg_node = self.cfg_model.find_node_by_ref(mrc)
        if cfg_node is not None:
            self.cfg_model.remove_node(cfg_node)

        hw_node  = self.hw_model.find_node_by_ref(mrc)
        if hw_node is not None:
            self.hw_model.remove_node(hw_node)

    ########## Device ########## 
    def _add_hw_device_node(self, device):
        if self.hw_model.find_node_by_ref(device) is not None:
            raise RuntimeError("Node exists")

        hw_node     = htm.DeviceNode(device)
        parent_node = self.hw_model.find_node_by_ref(device.mrc).children[device.bus]
        row = find_insertion_index(parent_node.children, lambda c: device.address < c.ref.address)
        self.hw_model.add_node(hw_node, parent_node, row)

    def _add_cfg_device_node(self, device):
        if self.cfg_model.find_node_by_ref(device) is not None:
            raise RuntimeError("Node exists")

        cfg_node    = ctm.DeviceNode(device)
        parent_node = self.cfg_model.find_node_by_ref(device.mrc).children[device.bus]
        row = find_insertion_index(parent_node.children, lambda c: device.address < c.ref.address)
        self.cfg_model.add_node(cfg_node, parent_node, row)

    def _device_added(self, device):
        self.log.debug("_device_added: %s", device)

        cfg_node = self.cfg_model.find_node_by_ref(device)
        if cfg_node is None and (self.linked_mode or device.cfg is not None):
            self._add_cfg_device_node(device)

        hw_node = self.hw_model.find_node_by_ref(device)
        if hw_node is None and (self.linked_mode or device.hw is not None):
            self._add_hw_device_node(device)

        device.hardware_set.connect(self._device_hardware_set)
        device.config_set.connect(self._device_config_set)

    def _device_hardware_set(self, device, old_hw, new_hw):
        node = self.hw_model.find_node_by_ref(device)

        if new_hw is None and not self.linked_mode:
            assert node is not None
            self.hw_model.remove_node(node)
        elif new_hw is not None and node is None:
            self._add_hw_device_node(device)

    def _device_config_set(self, device, old_cfg, new_cfg):
        node = self.cfg_model.find_node_by_ref(device)

        if new_cfg is None and not self.linked_mode:
            assert node is not None
            self.cfg_model.remove_node(node)
        elif new_cfg is not None and node is None:
            self._add_cfg_device_node(device)

    def _device_about_to_be_removed(self, device):
        self.log.debug("_device_about_to_be_removed: %s", device)
        cfg_node = self.cfg_model.find_node_by_ref(device)
        if cfg_node is not None:
            self.cfg_model.remove_node(cfg_node)

        hw_node  = self.hw_model.find_node_by_ref(device)
        if hw_node is not None:
            self.hw_model.remove_node(hw_node)

class MCTreeView(QtGui.QWidget):
    hw_context_menu_requested   = pyqtSignal(object, object, object, object) #: node, idx, position, view
    cfg_context_menu_requested  = pyqtSignal(object, object, object, object) #: node, idx, position, view
    node_selected               = pyqtSignal(object, object, object) #: node, idx, view
    hw_node_selected            = pyqtSignal(object, object, object) #: node, idx, view
    cfg_node_selected           = pyqtSignal(object, object, object) #: node, idx, view

    linked_mode_changed         = pyqtSignal(bool)

    def __init__(self, app_director, find_data_file, device_registry, linked_mode_on=False, parent=None):
        super(MCTreeView, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)

        self.app_director = app_director
        self._director  = MCTreeDirector(app_registry=app_director.registry,
                device_registry=device_registry, find_data_file=find_data_file,
                linked_mode_on=linked_mode_on)

        self.cfg_model = self._director.cfg_model
        self.hw_model  = self._director.hw_model

        self.cfg_view  = ConfigTreeView()
        self.cfg_view.setModel(self.cfg_model)
        self.cfg_model.rowsInserted.connect(self.cfg_view.expandAll)
        self.cfg_model.rowsInserted.connect(partial(self.cfg_view.resizeColumnToContents, 0))
        self.cfg_view.customContextMenuRequested.connect(self._cfg_context_menu)
        self.cfg_view.expanded.connect(self._cfg_expanded)
        self.cfg_view.collapsed.connect(self._cfg_collapsed)
        self.cfg_view.selectionModel().currentChanged.connect(self._cfg_selection_current_changed)

        self.hw_view   = HardwareTreeView()
        self.hw_view.setModel(self.hw_model)
        self.hw_model.rowsInserted.connect(self.hw_view.expandAll)
        self.hw_model.rowsInserted.connect(partial(self.hw_view.resizeColumnToContents, 0))
        self.hw_view.customContextMenuRequested.connect(self._hw_context_menu)
        self.hw_view.expanded.connect(self._hw_expanded)
        self.hw_view.collapsed.connect(self._hw_collapsed)
        self.hw_view.selectionModel().currentChanged.connect(self._hw_selection_current_changed)

        self.cfg_view.expandAll()
        self.hw_view.expandAll()

        self.splitter_buttons = QtGui.QWidget()
        splitter_buttons_layout = QtGui.QVBoxLayout(self.splitter_buttons)

        def add_splitter_button(b):
            # keeps buttons from expanding horizontally
            policy = b.sizePolicy()
            policy.setHorizontalPolicy(QtGui.QSizePolicy.Maximum)
            b.setSizePolicy(policy)
            splitter_buttons_layout.addWidget(b)
            return b

        link_icons = {
                True: QtGui.QIcon(QtGui.QPixmap(find_data_file('mesycontrol/ui/link-intact-2x.png'))),
                False: QtGui.QIcon(QtGui.QPixmap(find_data_file('mesycontrol/ui/link-broken-2x.png')))
                }

        link_button = QtGui.QPushButton(link_icons[self.linked_mode], str())
        link_button.setCheckable(True)
        link_button.setChecked(self.linked_mode)

        def toggle_linked_mode():
            self.linked_mode = not self.linked_mode
            link_button.setIcon(link_icons[self.linked_mode])

        link_button.toggled.connect(toggle_linked_mode)
        link_button.setToolTip("Link Hardware & Config Views")

        add_splitter_button(link_button)

        splitter_buttons_layout.addStretch()
        splitter_buttons_layout.setContentsMargins(0, 0, 0, 0)
        splitter_buttons_layout.setSizeConstraint(QtGui.QLayout.SetMaximumSize)

        splitter = DoubleClickSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.hw_view)
        splitter.addWidget(self.splitter_buttons)
        splitter.addWidget(self.cfg_view)

        def on_handle_double_clicked():
            # make hw and cfg views the same size which will result in the
            # splitter buttons being centered
            sizes = splitter.sizes()
            size  = (sizes[0] + sizes[2]) / 2
            sizes[0], sizes[2] = size, size
            splitter.setSizes(sizes)

        splitter.handle(1).doubleClicked.connect(on_handle_double_clicked)
        splitter.handle(2).doubleClicked.connect(on_handle_double_clicked)

        layout = QtGui.QGridLayout(self)
        layout.addWidget(splitter, 0, 0)

    def set_linked_mode(self, on_off):
        if self.linked_mode != on_off:
            self._director.set_linked_mode(on_off)
            self.linked_mode_changed.emit(self.linked_mode)

    def get_linked_mode(self):
        return self._director.linked_mode

    linked_mode = pyqtProperty(bool, get_linked_mode, set_linked_mode, notify=linked_mode_changed)

    def _cfg_context_menu(self, pos):
        idx  = self.cfg_view.indexAt(pos)
        node = idx.internalPointer()
        self.cfg_context_menu_requested.emit(node, idx, pos, self.cfg_view)

    def _hw_context_menu(self, pos):
        idx  = self.hw_view.indexAt(pos)
        node = idx.internalPointer()
        self.hw_context_menu_requested.emit(node, idx, pos, self.hw_view)

    def cfg_idx_for_hw_idx(self, hw_idx):
        return self._director.cfg_idx_for_hw_idx(hw_idx)

    def hw_idx_for_cfg_idx(self, cfg_idx):
        return self._director.hw_idx_for_cfg_idx(cfg_idx)

    def _cfg_expanded(self, idx):
        if self.linked_mode and idx.internalPointer() is not self.cfg_model.root:
            self.hw_view.expand(self.hw_idx_for_cfg_idx(idx))

    def _hw_expanded(self, idx):
        if self.linked_mode and idx.internalPointer() is not self.hw_model.root:
            self.cfg_view.expand(self.cfg_idx_for_hw_idx(idx))

    def _cfg_collapsed(self, idx):
        if self.linked_mode:
            self.hw_view.collapse(self.hw_idx_for_cfg_idx(idx))

    def _hw_collapsed(self, idx):
        if self.linked_mode:
            self.cfg_view.collapse(self.cfg_idx_for_hw_idx(idx))

    def _cfg_selection_current_changed(self, current, previous):
        node = current.internalPointer()
        idc_conflict = isinstance(node, ctm.DeviceNode) and node.ref.idc_conflict

        if self.linked_mode and not idc_conflict:
            self.hw_view.setCurrentIndex(self.hw_idx_for_cfg_idx(current))
        else:
            self.hw_view.clearSelection()
        self.node_selected.emit(node, current, self.cfg_view)
        self.cfg_node_selected.emit(node, current, self.cfg_view)

    def _hw_selection_current_changed(self, current, previous):
        node = current.internalPointer()
        idc_conflict = isinstance(node, htm.DeviceNode) and node.ref.idc_conflict

        if self.linked_mode and not idc_conflict:
            self.cfg_view.setCurrentIndex(self.cfg_idx_for_hw_idx(current))
        else:
            self.cfg_view.clearSelection()

        self.node_selected.emit(node, current, self.hw_view)
        self.hw_node_selected.emit(node, current, self.hw_view)

class DoubleClickSplitterHandle(QtGui.QSplitterHandle):
    """Double click support for QSplitterHandle.
    Emits the doubleClicked signal if a double click occured on the handle and
    the mouse button is released within 200ms (if the mouse button is not
    released the user is most likely dragging the handle).
    """

    doubleClicked = pyqtSignal()

    def __init__(self, orientation, parent):
        super(DoubleClickSplitterHandle, self).__init__(orientation, parent)
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(200)

    def mouseDoubleClickEvent(self, event):
        self.timer.start()

    def mouseReleaseEvent(self, event):
        if self.timer.isActive():
            self.timer.stop()
            self.doubleClicked.emit()

    def sizeHint(self):
        return QtCore.QSize(2, 4)

class DoubleClickSplitter(QtGui.QSplitter):
    """QSplitter using DoubleClickSplitterHandles."""
    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super(DoubleClickSplitter, self).__init__(orientation, parent)

    def createHandle(self):
        return DoubleClickSplitterHandle(self.orientation(), self)

