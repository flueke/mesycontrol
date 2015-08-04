#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
import collections
import copy
import logging
import sys
import weakref

import pyqtgraph.console
pg = pyqtgraph

from qt import Qt
from qt import QtCore
from qt import QtGui

from basic_model import IDCConflict
from gui_util import is_setup, is_registry, is_mrc, is_bus, is_device, is_device_cfg, is_device_hw
from gui_util import is_config
from model_util import add_mrc_connection
from util import make_icon
import app_model as am
import basic_model as bm
import config_gui
import config_tree_model as ctm
import device_tableview
import future
import gui_util
import hardware_tree_model as htm
import resources
import util

log = logging.getLogger(__name__)

# TODO: enable/disable display actions on hw/cfg state change , closed, ...)

class GUIApplication(QtCore.QObject):
    """GUI logic"""
    def __init__(self, context, mainwindow):
        super(GUIApplication, self).__init__()
        self.log            = util.make_logging_source_adapter(__name__, self)
        self._mainwindow    = weakref.ref(mainwindow)
        self.context        = context
        self._linked_mode   = False
        self._device_window_map = dict() # app_model.Device -> list of QMdiSubWindow
        self._previous_tree_node = None  # The previously selected tree node
        self._selected_tree_node = None  # The currently selected tree node
        self._selected_device    = None  # The currently selected device or None if no device is selected
        self._previous_subwindow = None
        self._current_subwindow  = None
        self._subwindow_toolbar  = None

        self.mainwindow.installEventFilter(self)
        self.mainwindow.mdiArea.subWindowActivated.connect(self._on_subwindow_activated)

        # Treeview
        self.treeview = self.mainwindow.treeview

        self.treeview.cfg_context_menu_requested.connect(self._cfg_context_menu)
        self.treeview.hw_context_menu_requested.connect(self._hw_context_menu)

        self.treeview.node_activated.connect(self._tree_node_activated)
        self.treeview.node_selected.connect(self._tree_node_selected)

        # Logview setup: show logged and unhandled exceptions in the log view
        self.logview = self.mainwindow.logview
        sys.excepthook.register_handler(self.logview.handle_exception)
        callback_handler = util.CallbackHandler()
        callback_handler.addFilter(util.MinimumLevelFilter(logging.ERROR))
        callback_handler.addFilter(util.HasExceptionFilter())
        callback_handler.add_callback(self.logview.handle_log_record)
        logging.getLogger().addHandler(callback_handler)

        # Load device modules
        context.init_device_registry()

        # Clean resources on exit
        context.add_shutdown_callback(resources.qCleanupResources)

        # Actions
        self._create_actions()
        self._populate_menus()
        self._populate_toolbar()
        self._populate_treeview()

        # Model changes
        self.app_registry.hw.mrc_added.connect(self._hw_mrc_added)
        self.app_registry.config_set.connect(self._setup_changed)

        # Init
        self._setup_changed(self.app_registry, None, self.app_registry.cfg)
        self._update_actions()

        #self._tree_node_selected(None)

    def _setup_changed(self, app_registry, old, new):
        if old:
            old.modified_changed.disconnect(self._update_actions)

        if new:
            new.modified_changed.connect(self._update_actions)

        self._update_actions()

    def _create_actions(self):
        # Actions will be added to toolbars in dictionary insertion order.
        self.actions = collections.OrderedDict()

        # ===== Config ===== #

        # Open setup
        action = QtGui.QAction(make_icon(":/open-setup.png"),
                "&Open setup", self, triggered=self._open_setup)

        action.setToolTip("Open a setup file")
        action.setStatusTip(action.toolTip())
        action.setShortcut(QtGui.QKeySequence.Open)
        action.cfg_toolbar = True
        self.actions['open_setup'] = action

        # Save setup
        action = QtGui.QAction(make_icon(":/save-setup.png"),
                "&Save setup", self, triggered=self._save_setup)

        action.setToolTip("Save setup")
        action.setStatusTip(action.toolTip())
        action.setShortcut(QtGui.QKeySequence.Save)
        action.cfg_toolbar = True
        self.actions['save_setup'] = action

        # Save setup as
        action = QtGui.QAction(make_icon(":/save-setup-as.png"),
                "S&ave setup as", self, triggered=self._save_setup_as)

        action.setToolTip("Save setup as")
        action.setStatusTip(action.toolTip())
        action.setShortcut(QtGui.QKeySequence.SaveAs)
        action.cfg_toolbar = True
        self.actions['save_setup_as'] = action

        # Close setup
        action = QtGui.QAction(make_icon(":/close-setup.png"),
                "&Close setup", self, triggered=self._close_setup)

        action.setToolTip("Close setup")
        action.setStatusTip(action.toolTip())
        action.cfg_toolbar = True
        self.actions['close_setup'] = action

        # Add config
        action = QtGui.QAction(make_icon(":/add-config.png"), "Add config", self,
                triggered=self._add_config)
        action.cfg_toolbar = True
        self.actions['add_config'] = action

        # Remove config
        action = QtGui.QAction(make_icon(":/remove-config.png"), "Remove config", self,
                triggered=self._remove_config)
        action.cfg_toolbar = True
        self.actions['remove_config'] = action

        action = QtGui.QAction("Rename", self,
                triggered=self._rename_config)
        self.actions['rename_config'] = action

        # Open device config
        action = QtGui.QAction(QtGui.QIcon.fromTheme("document-open"),
                "Open device config", self, triggered=self._open_device_config)
        self.actions['open_device_config'] = action

        # Save device config
        action = QtGui.QAction(QtGui.QIcon.fromTheme("document-save"),
                "Save device config", self, triggered=self._save_device_config)
        self.actions['save_device_config'] = action

        # ===== Hardware ===== #

        # Connect/Disconnect
        icons = {
                'connect':      make_icon(":/connect.png"),
                'disconnect':   make_icon(":/disconnect.png")
                }

        action = QtGui.QAction(icons['connect'], "&Connect", self,
                triggered=self._connect_or_disconnect)
        action.icons = icons
        action.hw_toolbar = True
        self.actions['connect_disconnect'] = action

        # Refresh / Scanbus
        # FIXME: what does this do? split into scanbus and refresh?!?!?!
        #action = QtGui.QAction(make_icon(":/refresh.png"), "&Refresh", self,
        #        triggered=self._refresh)
        #action.hw_toolbar = True
        #self.actions['refresh'] = action

        # Toggle polling
        action = QtGui.QAction(make_icon(":/polling.png"), "Toggle Polling", self,
                checkable=True, triggered=self._toggle_polling)
        action.hw_toolbar = True
        self.actions['toggle_polling'] = action

        # Toggle RC
        action = QtGui.QAction(make_icon(":/remote-control.png"), "Toggle RC", self,
                checkable=True, triggered=self._toggle_rc)
        action.hw_toolbar = True
        self.actions['toggle_rc'] = action

        # Add connection
        action = QtGui.QAction(make_icon(":/add-mrc.png"), "Add MRC connection", self,
                triggered=self._add_mrc_connection)
        action.hw_toolbar = True
        self.actions['add_mrc_connection'] = action

        # Remove connection
        action = QtGui.QAction(make_icon(":/remove-mrc.png"), "Remove MRC connection", self,
                triggered=self._remove_mrc_connection)
        action.hw_toolbar = True
        self.actions['remove_mrc_connection'] = action

        # ===== Splitter =====
        # Linked Mode
        link_icons = {
                True:  make_icon(":/linked.png"),
                False: make_icon(":/unlinked.png")
                }

        action = QtGui.QAction(link_icons[self.linked_mode], "Toggle linked mode",
                self, toggled=self.set_linked_mode)

        action.icons = link_icons
        action.setToolTip("Link Hardware & Config Views")
        action.setStatusTip(action.toolTip())
        action.setCheckable(True)
        action.setChecked(self.linked_mode)
        action.splitter_toolbar = True
        self.actions['toggle_linked_mode'] = action

        # Widget window
        action = QtGui.QAction(make_icon(":/open-device-widget.png"),
                "Open device widget", self, triggered=self._open_device_widget)

        action.setToolTip("Open device widget")
        action.setStatusTip(action.toolTip())
        action.splitter_toolbar = True
        self.actions['open_device_widget'] = action

        # Table window
        action = QtGui.QAction(make_icon(":/open-device-table.png"),
                "Open device table", self, triggered=self._open_device_table)

        action.setToolTip("Open device table")
        action.setStatusTip(action.toolTip())
        action.splitter_toolbar = True
        self.actions['open_device_table'] = action

        # Check config
        action = QtGui.QAction(make_icon(":/check-config.png"), "Check config", self,
                triggered=self._check_config)
        action.splitter_toolbar = True
        self.actions['check_config'] = action

        # Config to Hardware
        action = QtGui.QAction(make_icon(":/apply-config-to-hardware.png"),
                "Apply config to hardware", self, triggered=self._apply_config_to_hardware)
        action.splitter_toolbar = True
        self.actions['apply_config_to_hardware'] = action

        # Hardware to Config
        action = QtGui.QAction(make_icon(":/apply-hardware-to-config.png"),
                "Copy hardware values to config", self, triggered=self._apply_hardware_to_config)
        action.splitter_toolbar = True
        self.actions['apply_hardware_to_config'] = action

        # ===== Mainwindow toolbar =====

        # Display mode
        group = QtGui.QActionGroup(self)
        self.actions['display_hw']          = QtGui.QAction("Hardware", group,
                checkable=True, enabled=False, toggled=self._on_display_hw_toggled)
        self.actions['display_cfg']         = QtGui.QAction("Config", group,
                checkable=True, enabled=False, toggled=self._on_display_cfg_toggled)
        self.actions['display_combined']    = QtGui.QAction("Combined", group,
                checkable=True, enabled=False, toggled=self._on_display_combined_toggled)

        action = QtGui.QAction(make_icon(":/select-display-mode.png"),
                "Set display mode", self, enabled=False)

        action.setToolTip("Toggle display mode")
        action.setStatusTip(action.toolTip())
        action.toolbar = True
        action.setMenu(QtGui.QMenu())
        action.menu().addActions(group.actions())
        self.actions['select_display_mode'] = action

        # Write mode
        group = QtGui.QActionGroup(self)
        self.actions['write_hw']            = QtGui.QAction("Hardware", group,
                checkable=True, enabled=False, toggled=self._on_write_hw_toggled)
        self.actions['write_cfg']           = QtGui.QAction("Config", group,
                checkable=True, enabled=False, toggled=self._on_write_cfg_toggled)
        self.actions['write_combined']      = QtGui.QAction("Combined", group,
                checkable=True, enabled=False, toggled=self._on_write_combined_toggled)

        action = QtGui.QAction(make_icon(":/select-write-mode.png"),
                "Set write mode", self, enabled=False)

        action.setToolTip("Toggle write mode")
        action.setStatusTip(action.toolTip())
        action.toolbar = True
        action.setMenu(QtGui.QMenu())
        action.menu().addActions(group.actions())
        self.actions['select_write_mode'] = action

        # Quit
        action = QtGui.QAction("&Quit", self, triggered=self.mainwindow.close)
        action.setShortcut(QtGui.QKeySequence.Quit)
        action.setShortcutContext(Qt.ApplicationShortcut)
        self.actions['quit'] = action

        # Next Window
        action = QtGui.QAction("&Next Window", self,
                triggered=self.mainwindow.mdiArea.activateNextSubWindow)
        action.setShortcut(QtGui.QKeySequence.NextChild)
        self.actions['next_window'] = action

        # Previous Window
        action = QtGui.QAction("&Previous Window", self,
                triggered=self.mainwindow.mdiArea.activatePreviousSubWindow)
        action.setShortcut(QtGui.QKeySequence.PreviousChild)
        self.actions['previous_window'] = action

        # Cascade Windows
        action = QtGui.QAction("&Cascade Windows", self,
                triggered=self.mainwindow.mdiArea.cascadeSubWindows)
        self.actions['cascade_windows'] = action

        # Tile Windows
        action = QtGui.QAction("&Tile Windows", self,
                triggered=self.mainwindow.mdiArea.tileSubWindows)
        self.actions['tile_windows'] = action

        # Close all windows
        action = QtGui.QAction("Cl&ose all Windows", self,
                triggered=self.mainwindow.mdiArea.closeAllSubWindows)
        self.actions['close_all_windows'] = action

    def _populate_menus(self):
        menu_file = self.mainwindow.menu_file
        menu_file.addAction(self.actions['open_setup'])
        menu_file.addAction(self.actions['save_setup'])
        menu_file.addAction(self.actions['save_setup_as'])
        menu_file.addAction(self.actions['close_setup'])
        menu_file.addSeparator()
        menu_file.addAction(self.actions['quit'])

        menu_window = self.mainwindow.menu_window
        menu_window.addAction(self.actions['next_window'])
        menu_window.addAction(self.actions['previous_window'])
        menu_window.addSeparator()
        menu_window.addAction(self.actions['cascade_windows'])
        menu_window.addAction(self.actions['tile_windows'])
        menu_window.addSeparator()
        menu_window.addAction(self.actions['close_all_windows'])

    def _populate_toolbar(self):
        tb = self.mainwindow.toolbar
        f  = lambda a: getattr(a, 'toolbar', False)

        for action in filter(f, self.actions.values()):
            tb.addAction(action)
            if action.menu() is not None:
                tb.widgetForAction(action).setPopupMode(QtGui.QToolButton.InstantPopup)

    def _populate_treeview(self):
        # Splitter
        f = lambda a: getattr(a, 'splitter_toolbar', False)

        for action in filter(f, self.actions.values()):
            self.treeview.splitter_toolbar.addAction(action)

        # Config
        f = lambda a: getattr(a, 'cfg_toolbar', False)

        for action in filter(f, self.actions.values()):
            self.treeview.cfg_toolbar.addAction(action)

        # Hardware
        f = lambda a: getattr(a, 'hw_toolbar', False)

        for action in filter(f, self.actions.values()):
            self.treeview.hw_toolbar.addAction(action)

    def _update_actions(self):
        prev_node   = self._previous_tree_node
        node        = self._selected_tree_node
        prev_win    = self._previous_subwindow
        win         = self._current_subwindow

        setup = self.app_registry.cfg

        self.actions['save_setup'].setEnabled(setup.modified and len(setup))
        self.actions['save_setup_as'].setEnabled(len(setup))
        self.actions['close_setup'].setEnabled(len(setup))

        self.actions['remove_config'].setEnabled(
                (is_mrc(node) or is_device(node))
                and node.ref.has_cfg)

        self.actions['rename_config'].setEnabled(
                (is_mrc(node) or is_device(node)) and node.ref.has_cfg)

        self.actions['open_device_config'].setEnabled(is_device_cfg(node))
        self.actions['save_device_config'].setEnabled(is_device_cfg(node))

        a = self.actions['connect_disconnect']
        a.setEnabled((is_registry(node) and len(node.ref.hw)) or is_mrc(node))

        if a.isEnabled() and is_registry(node):
            if all(mrc.is_connected() for mrc in node.ref.hw):
                a.setIcon(a.icons['disconnect'])
                a.setToolTip("Disconnect all MRCs")
            else:
                a.setIcon(a.icons['connect'])
                a.setToolTip("Connect all MRCs")

            a.setText(a.toolTip())

        if a.isEnabled() and is_mrc(node):
            if node.ref.has_hw and node.ref.hw.is_connected():
                a.setIcon(a.icons['disconnect'])
                a.setToolTip("Disconnect")
            else:
                a.setIcon(a.icons['connect'])
                a.setToolTip("Connect")

        a = self.actions['toggle_polling']
        a.setEnabled((is_mrc(node) or is_device(node)) and node.ref.has_hw)

        if a.isEnabled():
            a.setChecked(node.ref.hw.polling)
            a.setToolTip("Disable polling" if a.isChecked() else "Enable polling")
            a.setText(a.toolTip())

        a = self.actions['toggle_rc']
        a.setEnabled(is_device(node) and node.ref.has_hw and not node.ref.hw.address_conflict)

        if a.isEnabled():
            a.setChecked(node.ref.hw.rc)
            a.setToolTip("Disable RC" if a.isChecked() else "Enable RC")
            a.setText(a.toolTip())

        self.actions['remove_mrc_connection'].setEnabled(is_mrc(node) and node.ref.has_hw)

        self.actions['toggle_linked_mode'].setChecked(self.linked_mode)

        self.actions['open_device_widget'].setEnabled(
                (is_device_cfg(node) and node.ref.cfg_module.has_widget_class()) or
                (is_device_hw(node) and node.ref.hw_module.has_widget_class()))

        self.actions['open_device_table'].setEnabled(is_device(node))

        self.actions['apply_config_to_hardware'].setEnabled(
                self.linked_mode
                and ((is_setup(node) and node.ref.has_cfg)
                    or (is_mrc(node) and node.ref.has_cfg)
                    or (is_bus(node) and node.parent.ref.has_cfg)
                    or (is_device(node)
                        and not node.ref.idc_conflict
                        and not node.ref.address_conflict
                        and node.ref.has_cfg)))

        self.actions['apply_hardware_to_config'].setEnabled(
                (is_setup(node) and node.ref.has_hw and len(node.ref.hw))
                or (is_mrc(node) and node.ref.has_hw and len(node.ref.hw))
                or (is_bus(node)
                    and node.parent.ref.has_hw
                    and len(node.parent.ref.hw.get_devices(node.bus_number)))
                or (is_device(node)
                    and not node.ref.idc_conflict
                    and not node.ref.address_conflict
                    and node.ref.has_hw))

        for a in self.actions.values():
            if len(a.toolTip()):
                a.setStatusTip(a.toolTip())

    def _tree_node_selected(self, node):
        self.log.debug("_tree_node_selected: %s", node)

        self._previous_tree_node = prev_node = self._selected_tree_node
        self._selected_tree_node = node
        self._selected_device    = node.ref if is_device(node) else None

        self._update_actions()

        hw_signals = [
                'address_conflict_changed',
                'polling_changed',
                'connected',
                'connecting',
                'disconnected',
                'connection_error'
                ]

        device_signals = [
                'idc_conflict_changed',
                'idc_changed',
                'cfg_idc_changed',
                'hw_idc_changed'
                ]

        app_signals = [
                'hardware_set',
                'config_set'
                ]

        if prev_node is not None:
            if (is_mrc(prev_node) or is_device(prev_node)) and prev_node.ref.has_hw:
                for sig in hw_signals:
                    try:
                        getattr(prev_node.ref.hw, sig).disconnect(self._update_actions)
                    except TypeError:
                        pass

            if is_device(prev_node):
                for sig in device_signals:
                    try:
                        getattr(prev_node.ref, sig).disconnect(self._update_actions)
                    except TypeError:
                        pass

            if isinstance(prev_node.ref, am.AppObject):
                for sig in app_signals:
                    try:
                        getattr(prev_node.ref, sig).disconnect(self._update_actions)
                    except TypeError:
                        pass

        if node is not None:
            if (is_mrc(node) or is_device(node)) and node.ref.has_hw:
                self.log.debug("_tree_node_selected: connecting hw_signals for node %s", node)
                for sig in hw_signals:
                    getattr(node.ref.hw, sig).connect(self._update_actions)

            if is_device(node):
                self.log.debug("_tree_node_selected: connecting device_signals for node %s", node)
                for sig in device_signals:
                    getattr(node.ref, sig).connect(self._update_actions)

            if isinstance(node.ref, am.AppObject):
                self.log.debug("_tree_node_selected: connecting app_signals for node %s", node)
                for sig in app_signals:
                    getattr(node.ref, sig).connect(self._update_actions)

        # XXX: leftoff

        # _setup_changed:
        #   modified_changed
        #
        # _on_subwindow_activated:
        #   select correct nodes
        #   check display mode of subwin
        #   enable/disable select_XXX_mode actions depending on subwin display
        #
        # _tree_node_selected:
        #   enable/disable actions depending on node type and state
        #   disconnect old node signals
        #   connect new node signals
        #
        # set_linked_mode
        #   update linked mode action depending on state

    # ===== Action implementations =====
    def _open_setup(self):
        gui_util.run_open_setup_dialog(context=self.context, parent_widget=self.mainwindow)

    def _save_setup(self):
        gui_util.run_save_setup(context=self.context, parent_widget=self.mainwindow)

    def _save_setup_as(self):
        gui_util.run_save_setup_as_dialog(context=self.context, parent_widget=self.mainwindow)

    def _close_setup(self):
        gui_util.run_close_setup(context=self.context, parent_widget=self.mainwindow)
        self.context.make_qsettings().remove('Files/last_setup_file')

    def _add_config(self):
        node = self._selected_tree_node

        if node is None or is_setup(node):
            gui_util.run_add_mrc_config_dialog(
                    registry=self.app_registry,
                    parent_widget=self.mainwindow)

        if is_mrc(node):
            gui_util.run_add_device_config_dialog(
                    registry=self.app_registry,
                    device_registry=self.context.device_registry,
                    mrc=node.ref,
                    parent_widget=self.mainwindow)

        if is_bus(node):
            gui_util.run_add_device_config_dialog(
                    registry=self.app_registry,
                    device_registry=self.context.device_registry,
                    mrc=node.parent.ref,
                    bus=node.bus_number,
                    parent_widget=self.mainwindow)

    def _remove_config(self):
        node = self._selected_tree_node

        if is_mrc(node):
            self.app_registry.cfg.remove_mrc(node.ref.cfg)

        if is_device(node):
            device = node.ref
            self._close_device_windows(device)
            device.mrc.cfg.remove_device(device.cfg)

    def _rename_config(self):
        node = self._selected_tree_node

        if (is_config(node) and
                (is_mrc(node) or is_device(node)) and
                node.ref.has_cfg):
            self.treeview.cfg_view.edit(
                    self.treeview.cfg_model.index_for_ref(node.ref))

    def _connect_or_disconnect(self):
        node = self._selected_tree_node
        a = self.actions['connect_disconnect']

        if is_mrc(node):
            if not node.ref.has_hw:
                add_mrc_connection(self.app_registry.hw, node.ref.url, True)
            elif node.ref.hw.is_disconnected():
                node.ref.hw.connect()
                a.setIcon(a.icons['disconnect'])
            else:
                node.ref.hw.disconnect()
                a.setIcon(a.icons['connect'])

    def _refresh(self):
        raise NotImplementedError()

    def _toggle_polling(self):
        node = self._selected_tree_node

        if (is_mrc(node) or is_device(node)) and node.ref.has_hw:
            node.ref.hw.polling = not node.ref.hw.polling

    def _toggle_rc(self):
        node = self._selected_tree_node

        if is_device(node) and node.ref.has_hw:
            node.ref.hw.set_rc(not node.ref.hw.rc)

    def _add_mrc_connection(self):
        gui_util.run_add_mrc_connection_dialog(
                registry=self.app_registry,
                parent_widget=self.mainwindow)

    def _remove_mrc_connection(self):
        node = self._selected_tree_node

        def do_remove(f_ignored):
            self.app_registry.hw.remove_mrc(node.ref.hw)

        node.ref.hw.disconnect().add_done_callback(do_remove)

    def _open_device_widget(self):
        node = self._selected_tree_node

        self._create_device_widget_window(self._selected_device,
                is_device_cfg(node), is_device_hw(node))

    def _open_device_table(self):
        node = self._selected_tree_node

        self._create_device_table_window(self._selected_device,
                is_device_cfg(node), is_device_hw(node))

    def _check_config(self):
        pass

    def _apply_config_to_hardware(self):
        node = self._selected_tree_node
        runner = None
        progress_dialog = None

        if is_setup(node):
            devices = [d for mrc in node.ref for d in mrc if d.has_cfg]

            runner = config_gui.ApplyDeviceConfigsRunner(
                    devices=devices,
                    parent_widget=self.mainwindow)

            progress_dialog = config_gui.SubProgressDialog()

        elif is_mrc(node):
            devices = [d for d in node.ref if d.has_cfg]

            runner = config_gui.ApplyDeviceConfigsRunner(
                    devices=devices,
                    parent_widget=self.mainwindow)

            progress_dialog = config_gui.SubProgressDialog()

        elif is_bus(node):
            devices = [d for d in node.parent.ref.get_devices(bus=node.bus_number) if d.has_cfg]

            runner = config_gui.ApplyDeviceConfigsRunner(
                    devices=devices,
                    parent_widget=self.mainwindow)

            progress_dialog = config_gui.SubProgressDialog()

        elif is_device(node):
            runner = config_gui.ApplyDeviceConfigsRunner(
                    devices=[node.ref],
                    parent_widget=self.mainwindow)

            progress_dialog = config_gui.SubProgressDialog()

        runner.progress_changed.connect(progress_dialog.set_progress)
        progress_dialog.canceled.connect(runner.close)
        f = runner.start()
        fo = future.FutureObserver(f)
        fo.done.connect(progress_dialog.close)
        progress_dialog.exec_()

        if f.done() and f.exception() is not None:
            log.error("Apply config: %s", f.exception())
            QtGui.QMessageBox.critical(self.mainwindow, "Error", str(f.exception()))

    def _apply_hardware_to_config(self):
        # FIXME: this does not work for MRCs that have never been connected as
        # the device list will be empty which will cause the runners generator
        # to do nothing. Instead of specifying the devices here a list of MRCs
        # could be passed and the list of devices would be built dynamically.

        node = self._selected_tree_node
        runner = None
        progress_dialog = None

        if is_registry(node):
            devices = [d for mrc in node.ref for d in mrc if d.has_hw]
            runner  = config_gui.FillDeviceConfigsRunner(
                    devices=devices, parent_widget=self.mainwindow)
            progress_dialog = config_gui.SubProgressDialog()
        elif is_mrc(node):
            devices = [d for d in node.ref if d.has_hw]
            runner  = config_gui.FillDeviceConfigsRunner(
                    devices=devices, parent_widget=self.mainwindow)
            progress_dialog = config_gui.SubProgressDialog()
        elif is_bus(node):
            devices = [d for d in node.parent.ref.get_devices(bus=node.bus_number) if d.has_hw]
            runner  = config_gui.FillDeviceConfigsRunner(
                    devices=devices, parent_widget=self.mainwindow)
            progress_dialog = config_gui.SubProgressDialog()
        elif is_device(node):
            devices = [node.ref]
            runner  = config_gui.FillDeviceConfigsRunner(
                    devices=devices, parent_widget=self.mainwindow)
            progress_dialog = config_gui.SubProgressDialog()

        runner.progress_changed.connect(progress_dialog.set_progress)
        progress_dialog.canceled.connect(runner.close)
        f = runner.start()
        fo = future.FutureObserver(f)
        fo.done.connect(progress_dialog.close)
        progress_dialog.exec_()

        if f.done() and f.exception() is not None:
            log.error("Fill config: %s", f.exception())
            QtGui.QMessageBox.critical(self.mainwindow, "Error", str(f.exception()))

    def _open_device_config(self):
        device = self._selected_tree_node.ref
        mrc    = device.mrc

        if gui_util.run_load_device_config(device=device, context=self.context,
                parent_widget=self.mainwindow):
            # If the device did not have a hardware model prior to loading the
            # config it will have been completely removed and a new
            # app_model.Device will have been created. Query the mrc to get the
            # newly created Device.
            device = mrc.get_device(device.bus, device.address)

            # Select the hardware node before the config node to end up
            # with focus in the config tree.
            if self.linked_mode and not device.idc_conflict:
                self.treeview.select_hardware_node_by_ref(device)

            self.treeview.select_config_node_by_ref(device)

    def _save_device_config(self):
        device = self._selected_tree_node.ref
        gui_util.run_save_device_config(device=device, context=self.context,
                parent_widget=self.mainwindow)

    def quit(self):
        """Non-blocking method to quit the application. Needs a running event
        loop."""
        QtCore.QMetaObject.invokeMethod(self.mainwindow, "close", Qt.QueuedConnection)

    def _on_subwindow_activated(self, window):
        if self._subwindow_toolbar is not None:
            self.mainwindow.removeToolBar(self._subwindow_toolbar)
            self._subwindow_toolbar = None

        act_display = self.actions['select_display_mode']
        act_write   = self.actions['select_write_mode']

        if isinstance(window, gui_util.DeviceSubWindow):
            device       = window.device
            display_mode = window.display_mode
            write_mode   = window.write_mode

            self.log.debug("_on_subwindow_activated: d=%s, has_hw=%s, has_cfg=%s, display_mode=%d, write_mode=%d",
                    device, device.has_hw, device.has_cfg, display_mode, write_mode)

            if display_mode & util.CONFIG:
                self.treeview.select_config_node_by_ref(device)
            elif display_mode & util.HARDWARE:
                self.treeview.select_hardware_node_by_ref(device)

            # Enable the parent actions
            act_display.setEnabled(True)
            act_write.setEnabled(True)

            if display_mode == util.COMBINED:
                self.actions['display_combined'].setChecked(True)
            elif display_mode == util.HARDWARE:
                self.actions['display_hw'].setChecked(True)
            else:
                self.actions['display_cfg'].setChecked(True)

            if write_mode == util.COMBINED:
                self.actions['write_combined'].setChecked(True)
            elif display_mode == util.HARDWARE:
                self.actions['write_hw'].setChecked(True)
            else:
                self.actions['write_cfg'].setChecked(True)

            self.actions['display_combined'].setEnabled(window.has_combined_display()
                    and device.has_hw and device.has_cfg)
            self.actions['write_combined'].setEnabled(device.has_hw and device.has_cfg)
            self.actions['display_hw'].setEnabled(device.has_hw)
            self.actions['write_hw'].setEnabled(device.has_hw)
            self.actions['display_cfg'].setEnabled(device.has_cfg)
            self.actions['write_cfg'].setEnabled(device.has_cfg)
        else:
            # Disable the parent actions
            act_display.setEnabled(False)
            act_write.setEnabled(False)

        if hasattr(window, 'has_toolbar') and window.has_toolbar():
            self._subwindow_toolbar = tb = window.get_toolbar()
            tb.setIconSize(QtCore.QSize(16, 16))
            tb.setWindowTitle("Subwindow Toolbar")
            tb.setObjectName("subwindow_toolbar")
            self.mainwindow.addToolBar(tb)
            tb.show()

    def active_subwindow(self):
        return self.mainwindow.mdiArea.activeSubWindow()

    # Note: The toggled() signal is emitted on user action _and_ on
    # setChecked() and similar calls. In contrast triggered() is only emitted
    # on user action.
    def _on_display_hw_toggled(self, b):
        if b:
            w = self.active_subwindow()
            w.display_mode = util.HARDWARE

    def _on_display_cfg_toggled(self, b):
        if b:
            w = self.active_subwindow()
            w.display_mode = util.CONFIG

    def _on_display_combined_toggled(self, b):
        if b:
            w = self.active_subwindow()
            w.display_mode = util.COMBINED

    def _on_write_hw_toggled(self, b):
        if b:
            w = self.active_subwindow()
            w.write_mode = util.HARDWARE

    def _on_write_cfg_toggled(self, b):
        if b:
            w = self.active_subwindow()
            w.write_mode = util.CONFIG

    def _on_write_combined_toggled(self, b):
        if b:
            w = self.active_subwindow()
            w.write_mode = util.COMBINED

    def _show_device_windows(self, device, show_cfg, show_hw):
        """Shows existing device windows. Return True if at least one window
        was shown, False otherwise."""
        if device not in self._device_window_map:
            self.log.debug("No window for %s", device)
            return False

        def window_filter(window):
            return ((show_cfg and window.display_mode & util.CONFIG)
                    or (show_hw and window.display_mode & util.HARDWARE))

        windows = filter(window_filter, self._device_window_map[device])

        self.log.debug("Found %d windows for %s", len(windows), device)

        for subwin in windows:
            if subwin.isMinimized():
                subwin.showNormal()
            self.mainwindow.mdiArea.setActiveSubWindow(subwin)

        return len(windows) > 0

    def _close_device_windows(self, device):
        for window in copy.copy(self._device_window_map.get(device, set())):
            window.close()

    def _tree_node_activated(self, node):
        if is_device(node):
            device = node.ref

            self._show_or_create_device_window(device,
                    is_device_cfg(node), is_device_hw(node))

    def _show_or_create_device_window(self, device, from_config_side, from_hw_side):
        if self._show_device_windows(device, from_config_side, from_hw_side):
            return

        try:
            module = device.module
        except IDCConflict:
            module = device.cfg_module if from_config_side else device.hw_module

        if module.has_widget_class():
            self._create_device_widget_window(device, from_config_side, from_hw_side)
        else:
            self._create_device_table_window(device, from_config_side, from_hw_side)

    def _create_device_table_window(self, app_device, from_config_side, from_hw_side):
        if self.linked_mode and not app_device.idc_conflict:
            display_mode = write_mode = util.COMBINED
        elif from_config_side:
            display_mode = write_mode = util.CONFIG
        elif from_hw_side:
            display_mode = write_mode = util.HARDWARE

        subwin = self._add_device_table_window(app_device, display_mode, write_mode)

        if subwin.isMinimized():
            subwin.showNormal()

    def _create_device_widget_window(self, app_device, from_config_side, from_hw_side):
        if self.linked_mode:
            if app_device.has_hw and app_device.has_cfg:
                write_mode = util.COMBINED
                read_mode  = util.CONFIG if from_config_side else util.HARDWARE
            elif app_device.has_hw:
                write_mode = read_mode = util.HARDWARE
            else:
                write_mode = read_mode = util.CONFIG
        else:
            write_mode = read_mode = util.CONFIG if from_config_side else util.HARDWARE

        subwin = self._add_device_widget_window(app_device, read_mode, write_mode)

        if subwin.isMinimized():
            subwin.showNormal()

    def get_mainwindow(self):
        return self._mainwindow()

    def set_linked_mode(self, linked_mode):
        if self._linked_mode == linked_mode:
            return

        self._linked_mode = bool(linked_mode)
        self.treeview.linked_mode = self.linked_mode
        action = self.actions['toggle_linked_mode']
        action.setIcon(action.icons[self.linked_mode])

        # TODO: linked mode transition
        if linked_mode:
            # transition to linked_mode
            # for each DeviceTableWidget: set its mode to linked mode
            pass
        else:
            # transition from linked_mode
            # close all DeviceTableWidgets
            pass

    def get_linked_mode(self):
        return self._linked_mode

    mainwindow      = property(get_mainwindow)
    app_registry    = property(lambda self: self.context.app_registry)
    device_registry = property(lambda self: self.context.device_registry)
    linked_mode     = property(get_linked_mode, set_linked_mode)

    # Logview updates from MRC connection state changes
    def _hw_mrc_added(self, mrc):
        self.log.debug("hw mrc added: %s", mrc.url)
        mrc.connecting.connect(partial(self._hw_mrc_connecting, mrc=mrc))
        mrc.disconnected.connect(partial(self._hw_mrc_disconnected, mrc=mrc))

    def _hw_mrc_connecting(self, f, mrc):
        self.logview.append("Connecting to %s" % mrc.get_display_url())
        def done(f):
            try:
                f.result()
                self.logview.append("Connected to %s" % mrc.get_display_url())
            except Exception as e:
                self.logview.append("Error connecting to %s: %s" % (mrc.get_display_url(), e))

        def progress(f):
            txt = f.progress_text()
            if txt:
                self.logview.append("%s: %s" % (mrc.get_display_url(), txt))

        f.add_done_callback(done).add_progress_callback(progress)

    def _hw_mrc_disconnected(self, mrc):
        self.logview.append("Disconnected from %s" % mrc.get_display_url())

    # Device table window creation
    def _add_device_table_window(self, device, display_mode, write_mode):
        self.log.debug("Adding device table for %s with display_mode=%d, write_mode=%d",
                device, display_mode, write_mode)

        widget = device_tableview.DeviceTableWidget(device, display_mode, write_mode)
        subwin = gui_util.DeviceTableSubWindow(widget=widget)
        return self._register_device_subwindow(subwin)

    def _add_device_widget_window(self, app_device, display_mode, write_mode):
        self.log.debug("Adding device widget for %s with display_mode=%d, write_mode=%d",
                app_device, display_mode, write_mode)

        widget = app_device.make_device_widget(display_mode, write_mode)
        subwin = gui_util.DeviceWidgetSubWindow(widget=widget)
        return self._register_device_subwindow(subwin)

    def _register_device_subwindow(self, subwin):
        self.log.debug("registering subwin %s for device %s", subwin, subwin.device)
        self.mainwindow.mdiArea.addSubWindow(subwin)
        subwin.installEventFilter(self)
        gui_util.restore_subwindow_state(subwin, self.context.make_qsettings())
        subwin.show()
        self._device_window_map.setdefault(subwin.device, set()).add(subwin)
        return subwin

    def _cfg_context_menu(self, node, idx, pos, view):
        menu = QtGui.QMenu()

        def add_action(action):
            if action.isEnabled():
                menu.addAction(action)

        if is_setup(node):
            add_action(self.actions['open_setup'])
            add_action(self.actions['save_setup'])
            add_action(self.actions['save_setup_as'])
            add_action(self.actions['close_setup'])
            menu.addSeparator()
            add_action(self.actions['add_config'])

        if is_mrc(node):
            add_action(self.actions['rename_config'])
            add_action(self.actions['add_config'])
            add_action(self.actions['remove_config'])

        if is_bus(node):
            add_action(self.actions['add_config'])

        if is_device(node):
            add_action(self.actions['open_device_widget'])
            add_action(self.actions['open_device_table'])
            add_action(self.actions['rename_config'])
            menu.addSeparator()
            add_action(self.actions['open_device_config'])
            if node.ref.has_cfg:
                add_action(self.actions['save_device_config'])
            add_action(self.actions['remove_config'])

        if not menu.isEmpty():
            menu.exec_(view.mapToGlobal(pos))

    def _hw_context_menu(self, node, idx, pos, view):
        menu = QtGui.QMenu()

        def add_action(action):
            if action.isEnabled():
                menu.addAction(action)

        if is_registry(node):
            add_action(self.actions['add_mrc_connection'])

        if is_mrc(node):
            add_action(self.actions['connect_disconnect'])
            add_action(self.actions['refresh'])
            add_action(self.actions['toggle_polling'])
            menu.addSeparator()
            add_action(self.actions['remove_mrc_connection'])

        if is_bus(node):
            add_action(self.actions['refresh'])

        if is_device(node):
            add_action(self.actions['open_device_widget'])
            add_action(self.actions['open_device_table'])
            add_action(self.actions['toggle_polling'])
            add_action(self.actions['refresh'])

        if not menu.isEmpty():
            menu.exec_(view.mapToGlobal(pos))

    def eventFilter(self, watched_object, event):
        if (event.type() == QtCore.QEvent.Close
                and isinstance(watched_object, QtGui.QMdiSubWindow)):

            gui_util.store_subwindow_state(watched_object, self.context.make_qsettings())

            if (hasattr(watched_object, 'device')
                    and watched_object.device in self._device_window_map):
                # Remove the subwindow from the set of device windows
                self.log.debug("removing subwin %s for device %s", watched_object, watched_object.device)
                self._device_window_map[watched_object.device].remove(watched_object)

        elif (event.type() == QtCore.QEvent.Close
                and watched_object is self.mainwindow):
            if not gui_util.run_close_setup(self.context, self.mainwindow):
                event.ignore()
                return True

        return False
