#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2016 mesytec GmbH & Co. KG <info@mesytec.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

__author__ = 'Florian Lüke'
__email__  = 'f.lueke@mesytec.com'

from functools import partial
import collections
import copy
import logging
import sys
import weakref

import pyqtgraph.console
pg = pyqtgraph

from mesycontrol.qt import Slot
from mesycontrol.qt import Qt
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui
from mesycontrol.qt import QtWidgets

from mesycontrol.basic_model import IDCConflict
from mesycontrol.gui_util import is_setup, is_registry, is_mrc, is_bus, is_device, is_device_cfg, is_device_hw, get_mrc
from mesycontrol.gui_util import is_config, is_hardware
from mesycontrol.model_util import add_mrc_connection
from mesycontrol.mrc_connection import IsConnected, IsConnecting
from mesycontrol.util import make_icon

import mesycontrol.mrc_connection as mrc_connection
import mesycontrol.app_model as am
import mesycontrol.async_util as async_util
import mesycontrol.config_gui as config_gui
import mesycontrol.config_util as config_util
import mesycontrol.device_tableview as device_tableview
import mesycontrol.future as future
import mesycontrol.gui_tutorial as gui_tutorial
import mesycontrol.gui_util as gui_util
import mesycontrol.hardware_util as hardware_util
import mesycontrol.resources as resources
import mesycontrol.util as util

log = logging.getLogger(__name__)

class GUIApplication(QtCore.QObject):
    """GUI logic"""

    TOOLBAR_ICON_SIZE = QtCore.QSize(12, 12)
    TOOLBAR_FONT_SIZE = 10

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
        self.mainwindow.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.mainwindow.toolbar.setIconSize(GUIApplication.TOOLBAR_ICON_SIZE)
        self.mainwindow.actionQuickstart.triggered.connect(self._show_quickstart)
        font = self.mainwindow.toolbar.font()
        font.setPixelSize(GUIApplication.TOOLBAR_FONT_SIZE)
        self.mainwindow.toolbar.setFont(font)

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
        callback_handler.addFilter(util.MinimumLevelFilter(logging.WARNING))
        #callback_handler.addFilter(util.HasExceptionFilter())
        callback_handler.add_callback(self.logview.handle_log_record)
        logging.getLogger().addHandler(callback_handler)

        # Load device modules
        context.init_device_registry()

        for mod in iter(context.device_registry.modules.values()):
            self.logview.append("Loaded device module '%s' (idc=%d, name=%s)" %
                    (mod.__name__, mod.idc, mod.profile.name))

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
        self.app_registry.mrc_added.connect(self._app_mrc_added)
        self.app_registry.mrc_about_to_be_removed.connect(self._app_mrc_about_to_be_removed)

        # Init
        self._setup_changed(self.app_registry, None, self.app_registry.cfg)
        self._update_actions()

        settings = self.context.make_qsettings()

        if settings.value('MainWindow/first_run', True, type=bool):
            settings.setValue('MainWindow/first_run', False)
            self._show_quickstart()

    @Slot(object, object, object)
    def _setup_changed(self, app_registry, old, new):
        if old:
            old.modified_changed.disconnect(self._update_actions)

        if new:
            new.modified_changed.connect(self._update_actions)

        self._update_actions()

    @Slot(object)
    def _app_mrc_added(self, mrc):
        mrc.device_added.connect(self._app_device_added)
        mrc.device_about_to_be_removed.connect(self._app_device_about_to_be_removed)

        for device in mrc:
            self._app_device_added(device)

    @Slot(object)
    def _app_mrc_about_to_be_removed(self, mrc):
        mrc.device_added.disconnect(self._app_device_added)
        mrc.device_about_to_be_removed.disconnect(self._app_device_about_to_be_removed)

    @Slot(object)
    def _app_device_added(self, device):
        device.hardware_set.connect(self._app_device_hardware_set)
        device.config_set.connect(self._app_device_config_set)

    @Slot(object)
    def _app_device_about_to_be_removed(self, device):
        device.hardware_set.disconnect(self._app_device_hardware_set)
        device.config_set.disconnect(self._app_device_config_set)

        for window in list(self._device_window_map.get(device, list())):
            window.close()

    @Slot(object, object, object)
    def _app_device_hardware_set(self, device, old, new):
        if device.idc_conflict:
            for window in list(self._device_window_map.get(device, list())):
                try:
                    if util.COMBINED in (window.display_mode, window.write_mode):
                        window.close()
                except AttributeError:
                    pass

    @Slot(object, object, object)
    def _app_device_config_set(self, device, old, new):
        if device.idc_conflict:
            for window in list(self._device_window_map.get(device, list())):
                try:
                    if util.COMBINED in (window.display_mode, window.write_mode):
                        window.close()
                except AttributeError:
                    pass

    def _create_actions(self):
        # Actions will be added to toolbars in dictionary insertion order.
        self.actions = collections.OrderedDict()

        # ===== Config ===== #

        # Open setup
        action = QtWidgets.QAction(make_icon(":/open-setup.png"),
                "&Open setup", self, triggered=self._open_setup)

        action.setToolTip("Open a setup file")
        action.setStatusTip(action.toolTip())
        action.setShortcut(QtGui.QKeySequence.Open)
        action.cfg_toolbar = True
        self.actions['open_setup'] = action

        # Save setup
        action = QtWidgets.QAction(make_icon(":/save-setup.png"),
                "&Save setup", self, triggered=self._save_setup)

        action.setToolTip("Save setup")
        action.setStatusTip(action.toolTip())
        action.setShortcut(QtGui.QKeySequence.Save)
        action.cfg_toolbar = True
        self.actions['save_setup'] = action

        # Save setup as
        action = QtWidgets.QAction(make_icon(":/save-setup-as.png"),
                "S&ave setup as", self, triggered=self._save_setup_as)

        action.setToolTip("Save setup as")
        action.setStatusTip(action.toolTip())
        action.setShortcut(QtGui.QKeySequence.SaveAs)
        action.cfg_toolbar = True
        self.actions['save_setup_as'] = action

        # Close setup
        action = QtWidgets.QAction(make_icon(":/close-setup.png"),
                "&Close setup", self, triggered=self._close_setup)

        action.setToolTip("Close setup")
        action.setStatusTip(action.toolTip())
        action.cfg_toolbar = True
        self.actions['close_setup'] = action

        # Add config
        action = QtWidgets.QAction(make_icon(":/add-config.png"), "Add config", self,
                triggered=self._add_config)
        action.cfg_toolbar = True
        self.actions['add_config'] = action

        # Remove config
        action = QtWidgets.QAction(make_icon(":/remove-config.png"), "Remove config", self,
                triggered=self._remove_config)
        action.cfg_toolbar = True
        self.actions['remove_config'] = action

        # Rename
        action = QtWidgets.QAction(make_icon(":/rename.png"), "Rename", self,
                triggered=self._rename_config)
        self.actions['rename_config'] = action

        # Open device config
        action = QtWidgets.QAction(make_icon(":/open-setup.png"),
                "Load device config from file", self, triggered=self._open_device_config)
        self.actions['open_device_config'] = action

        # Save device config
        action = QtWidgets.QAction(make_icon(":/save-setup.png"),
                "Save device config to file", self, triggered=self._save_device_config)
        self.actions['save_device_config'] = action

        # Edit MRC config / MRC Properties
        action = QtWidgets.QAction(QtGui.QIcon.fromTheme("document-properties"),
                "Properties", self, triggered=self._edit_mrc_config)
        self.actions['edit_mrc_config'] = action

        # Edit device config / device properties
        action = QtWidgets.QAction(QtGui.QIcon.fromTheme("document-properties"),
                "Properties", self, triggered=self._edit_device_config)
        self.actions['edit_device_config'] = action

        # ===== Hardware ===== #

        # Connect/Disconnect
        icons = {
                'connect':      make_icon(":/connect.png"),
                'disconnect':   make_icon(":/disconnect.png")
                }

        action = QtWidgets.QAction(icons['connect'], "&Connect", self,
                triggered=self._connect_or_disconnect)
        action.icons = icons
        action.hw_toolbar = True
        self.actions['connect_disconnect'] = action

        # Write access
        action = QtWidgets.QAction(make_icon(":/write-access.png"), "Toggle write access", self,
                checkable=True, triggered=self._toggle_write_access)
        action.hw_toolbar = True
        self.actions['toggle_write_access'] = action

        # Silent mode
        icons = {
                True:  make_icon(":/silent-mode-on.png"),
                False: make_icon(":/silent-mode-off.png")
                }
        action = QtWidgets.QAction(icons[False], "Toggle silent mode", self,
                checkable=True, triggered=self._toggle_silent_mode)
        action.icons = icons
        action.hw_toolbar = True
        self.actions['toggle_silent_mode'] = action

        # Toggle RC
        action = QtWidgets.QAction(make_icon(":/remote-control.png"), "Toggle RC", self,
                checkable=True, triggered=self._toggle_rc)
        action.hw_toolbar = True
        self.actions['toggle_rc'] = action

        # Refresh device memory
        action = QtWidgets.QAction(make_icon(":/refresh.png"), "&Refresh memory", self,
                triggered=self._refresh)
        action.hw_toolbar = True
        self.actions['refresh'] = action

        # Add connection
        action = QtWidgets.QAction(make_icon(":/add-mrc.png"), "Add MRC connection", self,
                triggered=self._add_mrc_connection)
        action.hw_toolbar = True
        self.actions['add_mrc_connection'] = action

        # Remove connection
        action = QtWidgets.QAction(make_icon(":/remove-mrc.png"), "Remove MRC connection", self,
                triggered=self._remove_mrc_connection)
        action.hw_toolbar = True
        self.actions['remove_mrc_connection'] = action

        # Show server output
        action = QtWidgets.QAction("View server log", self,
                triggered=self._view_server_log)
        self.actions['view_server_log'] = action

        # ===== Splitter =====
        # Linked Mode
        link_icons = {
                True:  make_icon(":/linked.png"),
                False: make_icon(":/unlinked.png")
                }

        action = QtWidgets.QAction(link_icons[self.linked_mode], "Toggle linked mode")
        action.toggled.connect(self.set_linked_mode)

        action.icons = link_icons
        action.setToolTip("Link Hardware & Config Views")
        action.setStatusTip(action.toolTip())
        action.setCheckable(True)
        action.setChecked(self.linked_mode)
        action.splitter_toolbar = True
        self.actions['toggle_linked_mode'] = action

        # Check config
        action = QtWidgets.QAction(make_icon(":/check-config.png"), "Compare cfg/hw", self,
                triggered=self._check_config)
        action.splitter_toolbar = True
        self.actions['check_config'] = action

        # Config to Hardware
        action = QtWidgets.QAction(make_icon(":/apply-config-to-hardware.png"),
                "Apply cfg to hw", self, triggered=self._apply_config_to_hardware)
        action.splitter_toolbar = True
        self.actions['apply_config_to_hardware'] = action

        # Hardware to Config
        action = QtWidgets.QAction(make_icon(":/apply-hardware-to-config.png"),
                "Copy hw values to cfg", self, triggered=self._apply_hardware_to_config)
        action.splitter_toolbar = True
        self.actions['apply_hardware_to_config'] = action

        # Widget window
        action = QtWidgets.QAction(make_icon(":/open-device-widget.png"),
                "Open device gui", self, triggered=self._open_device_widget)

        action.setToolTip("Open device widget")
        action.setStatusTip(action.toolTip())
        action.splitter_toolbar = True
        self.actions['open_device_widget'] = action

        # Table window
        action = QtWidgets.QAction(make_icon(":/open-device-table.png"),
                "Open device table", self, triggered=self._open_device_table)

        action.setToolTip("Open device table")
        action.setStatusTip(action.toolTip())
        action.splitter_toolbar = True
        self.actions['open_device_table'] = action

        # ===== Mainwindow toolbar =====

        # Display mode
        group = QtWidgets.QActionGroup(self)
        self.actions['display_hw'] = QtWidgets.QAction("Hardware", group, checkable=True, enabled=False)
        self.actions['display_hw'].triggered[bool].connect(self._on_display_hw_triggered)

        self.actions['display_cfg'] = QtWidgets.QAction("Config", group, checkable=True, enabled=False)
        self.actions['display_cfg'].triggered[bool].connect(self._on_display_cfg_triggered)

        self.actions['display_combined'] = QtWidgets.QAction("Combined", group, checkable=True, enabled=False)
        self.actions['display_combined'].triggered[bool].connect(self._on_display_combined_triggered)

        action = QtWidgets.QAction(make_icon(":/select-display-mode.png"),
                "Display mode", self, enabled=False)

        action.setToolTip("Select display mode")
        action.setStatusTip(action.toolTip())
        action.toolbar = True
        action.setMenu(QtWidgets.QMenu())
        action.menu().addActions(group.actions())
        self.actions['select_display_mode'] = action

        # Write mode
        group = QtWidgets.QActionGroup(self)
        self.actions['write_hw'] = QtWidgets.QAction("Hardware", group, checkable=True, enabled=False)
        self.actions['write_hw'].triggered[bool].connect(self._on_write_hw_triggered)

        self.actions['write_cfg'] = QtWidgets.QAction("Config", group, checkable=True, enabled=False)
        self.actions['write_cfg'].triggered[bool].connect(self._on_write_cfg_triggered)

        self.actions['write_combined'] = QtWidgets.QAction("Combined", group, checkable=True, enabled=False)
        self.actions['write_combined'].triggered[bool].connect(self._on_write_combined_triggered)

        action = QtWidgets.QAction(make_icon(":/select-write-mode.png"),
                "Write mode", self, enabled=False)

        action.setToolTip("Select write mode")
        action.setStatusTip(action.toolTip())
        action.toolbar = True
        action.setMenu(QtWidgets.QMenu())
        action.menu().addActions(group.actions())
        self.actions['select_write_mode'] = action

        # Quit
        action = QtWidgets.QAction("&Quit", self, triggered=self.mainwindow.close)
        action.setShortcut("Ctrl+Q")
        action.setShortcutContext(Qt.ApplicationShortcut)
        self.actions['quit'] = action

        # Next Window
        action = QtWidgets.QAction("&Next Window", self,
                triggered=self.mainwindow.mdiArea.activateNextSubWindow)
        action.setShortcut(QtGui.QKeySequence.NextChild)
        self.actions['next_window'] = action

        # Previous Window
        action = QtWidgets.QAction("&Previous Window", self,
                triggered=self.mainwindow.mdiArea.activatePreviousSubWindow)
        action.setShortcut(QtGui.QKeySequence.PreviousChild)
        self.actions['previous_window'] = action

        # Cascade Windows
        action = QtWidgets.QAction("&Cascade Windows", self,
                triggered=self.mainwindow.mdiArea.cascadeSubWindows)
        self.actions['cascade_windows'] = action

        # Tile Windows
        action = QtWidgets.QAction("&Tile Windows", self,
                triggered=self.mainwindow.mdiArea.tileSubWindows)
        self.actions['tile_windows'] = action

        # Close all windows
        action = QtWidgets.QAction("Cl&ose all Windows", self,
                triggered=self.mainwindow.mdiArea.closeAllSubWindows)
        self.actions['close_all_windows'] = action

        # Edit extensions
        action = QtWidgets.QAction("Show device extensions", self,
                triggered=self._show_device_extensions)
        self.actions['show_device_extensions'] = action

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
                tb.widgetForAction(action).setPopupMode(QtWidgets.QToolButton.InstantPopup)

    def _populate_treeview(self):
        # Splitter
        f = lambda a: getattr(a, 'splitter_toolbar', False)

        for action in filter(f, self.actions.values()):
            button = self.treeview.splitter_toolbar.addAction(action)
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        # Config
        f = lambda a: getattr(a, 'cfg_toolbar', False)

        for action in filter(f, self.actions.values()):
            self.treeview.cfg_toolbar.addAction(action)

        # Hardware
        f = lambda a: getattr(a, 'hw_toolbar', False)

        for action in filter(f, self.actions.values()):
            self.treeview.hw_toolbar.addAction(action)


    def _update_actions_cb(self, *args, **kwargs):
        """Calls _update_actions(), ignoring args and kwargs. Usable as a
        Future callback."""
        return self._update_actions()

    @Slot()
    def _update_actions(self):
        node = self._selected_tree_node

        self.log.debug("update actions: selected=%s", node)

        setup = self.app_registry.cfg

        self.actions['save_setup'].setEnabled(setup.modified and len(setup))
        self.actions['save_setup_as'].setEnabled(len(setup))
        self.actions['close_setup'].setEnabled(len(setup))

        a = self.actions['add_config']
        a.setEnabled(node is None or is_config(node))

        if is_setup(node):
            a.setText("Add MRC")
        else:
            a.setText("Add Device")

        a = self.actions['remove_config']
        a.setEnabled((is_mrc(node) or is_device(node)) and node.ref.has_cfg
                and (self.linked_mode or is_config(node)))

        if a.isEnabled() and is_mrc(node):
            a.setText("Remove MRC config")

        if a.isEnabled() and is_device(node):
            a.setText("Remove Device config")

        self.actions['rename_config'].setEnabled(
                (is_mrc(node) or is_device(node)) and node.ref.has_cfg)

        self.actions['open_device_config'].setEnabled(is_device(node))
        self.actions['save_device_config'].setEnabled(is_device(node))

        a = self.actions['connect_disconnect']
        a.setEnabled((is_registry(node) and len(node.children)) or is_mrc(node))

        if a.isEnabled() and is_registry(node):
            if all((mrc.has_hw and mrc.hw.is_connected()) for mrc in node.ref):
                a.setIcon(a.icons['disconnect'])
                a.setToolTip("Disconnect all MRCs")
            else:
                a.setIcon(a.icons['connect'])
                a.setToolTip("Connect all MRCs")

            a.setText(a.toolTip())
            a.setStatusTip(a.toolTip())

        if a.isEnabled() and is_mrc(node):
            if node.ref.has_hw and node.ref.hw.is_connected():
                a.setIcon(a.icons['disconnect'])
                a.setToolTip("Disconnect")
            else:
                a.setIcon(a.icons['connect'])
                a.setToolTip("Connect")

            a.setText(a.toolTip())
            a.setStatusTip(a.toolTip())

        # Toggle RC
        a = self.actions['toggle_rc']
        a.setEnabled(is_device(node) and node.ref.has_hw and not node.ref.hw.address_conflict
            and (is_hardware(node) or self.linked_mode))

        a.setEnabled(is_device(node)
                and (is_hardware(node) or self.linked_mode)
                and node.ref.has_hw
                and node.ref.hw.is_connected()
                and node.ref.hw.mrc.write_access
                and not node.ref.hw.address_conflict)

        if a.isEnabled():
            a.setChecked(node.ref.hw.rc)
            a.setToolTip("Disable RC" if a.isChecked() else "Enable RC")
            a.setText(a.toolTip())
            a.setStatusTip(a.toolTip())

        # Refresh device memory
        a = self.actions['refresh']
        a.setEnabled(is_hardware(node))

        # Write access
        mrc = get_mrc(node)

        a = self.actions['toggle_write_access']

        a.setEnabled(mrc is not None
                and mrc.has_hw
                and (is_hardware(node) or self.linked_mode)
                and mrc.hw.is_connected())

        a.setChecked(a.isEnabled() and mrc.hw.write_access)

        if a.isChecked():
            a.setToolTip("Release write access")
        else:
            a.setToolTip("Acquire write access")

        a.setText(a.toolTip())
        a.setStatusTip(a.toolTip())

        # Silent mode
        enabled = (mrc is not None
                and mrc.has_hw
                and (is_hardware(node) or self.linked_mode)
                and mrc.hw.is_connected()
                and mrc.hw.write_access)

        checked = (mrc is not None
                and mrc.has_hw
                and mrc.hw.silenced)

        a = self.actions['toggle_silent_mode']

        a.setEnabled(enabled)
        a.setChecked(checked)

        a.setIcon(a.icons[a.isChecked()])

        if a.isChecked():
            a.setToolTip("Disable silent mode")
        else:
            a.setToolTip("Enable silent mode")

        a.setText(a.toolTip())
        a.setStatusTip(a.toolTip())

        # Remove connection
        a = self.actions['remove_mrc_connection']
        a.setEnabled(is_mrc(node)
                and (is_hardware(node) or self.linked_mode)
                and node.ref.has_hw)

        a = self.actions['toggle_linked_mode']
        a.setChecked(self.linked_mode)
        a.setIcon(a.icons[self.linked_mode])

        # Open device widget
        self.actions['open_device_widget'].setEnabled(
                ((is_device_cfg(node) and node.ref.cfg_module.has_widget_class())
                    or (is_device_hw(node) and node.ref.hw_module.has_widget_class()
                        and (not node.ref.has_hw or not node.ref.hw.address_conflict))))

        # Open device table
        self.actions['open_device_table'].setEnabled(
                is_device_cfg(node)
                or (is_device_hw(node)
                    and (not node.ref.has_hw or not node.ref.hw.address_conflict)))

        self.actions['apply_config_to_hardware'].setEnabled(
                ((is_setup(node) and node.ref.has_cfg)
                    or (is_mrc(node) and node.ref.has_cfg)
                    or (is_bus(node)
                        and node.parent is not None
                        and node.parent.ref.has_cfg)
                    or (is_device(node)
                        and not node.ref.idc_conflict
                        and not node.ref.address_conflict
                        and node.ref.has_cfg
                        and node.ref.has_hw)))

        self.actions['apply_hardware_to_config'].setEnabled(
                (is_setup(node) and node.ref.has_hw and node.ref.hw.contains_devices())
                or (is_mrc(node) and node.ref.has_hw and len(node.ref.hw))
                or (is_bus(node)
                    and node.parent is not None
                    and node.parent.ref.has_hw
                    and len(node.parent.ref.hw.get_devices(node.bus_number)))
                or (is_device(node)
                    and not node.ref.idc_conflict
                    and not node.ref.address_conflict
                    and node.ref.has_hw))

        win = self._current_subwindow

        act_display  = self.actions['select_display_mode']
        act_write    = self.actions['select_write_mode']

        if isinstance(win, gui_util.DeviceSubWindow):
            try:
                device = win.device
            except RuntimeError:
                device = None # c++ subwin might've been deleted
            display_mode = win.display_mode
            write_mode   = win.write_mode

            # Enable the parent actions
            act_display.setEnabled(True)
            act_write.setEnabled(True)

            act_display.setText(util.RW_MODE_NAMES[win.display_mode].capitalize())
            act_write.setText(util.RW_MODE_NAMES[win.write_mode].capitalize())

            if display_mode == util.COMBINED:
                self.actions['display_combined'].setChecked(True)
            elif display_mode == util.HARDWARE:
                self.actions['display_hw'].setChecked(True)
            else:
                self.actions['display_cfg'].setChecked(True)

            if write_mode == util.COMBINED:
                self.actions['write_combined'].setChecked(True)
            elif write_mode == util.HARDWARE:
                self.actions['write_hw'].setChecked(True)
            else:
                self.actions['write_cfg'].setChecked(True)

            self.actions['display_combined'].setEnabled(win.has_combined_display()
                    and device.has_hw and device.has_cfg and not device.idc_conflict)

            self.actions['write_combined'].setEnabled(device.has_hw and device.has_cfg
                    and not device.idc_conflict)

            self.actions['display_hw'].setEnabled(device.has_hw
                    and (not device.idc_conflict or display_mode == util.HARDWARE))

            self.actions['write_hw'].setEnabled(device.has_hw
                    and (not device.idc_conflict or display_mode == util.HARDWARE))

            self.actions['display_cfg'].setEnabled(device.has_cfg
                    and (not device.idc_conflict or display_mode == util.CONFIG))
            self.actions['write_cfg'].setEnabled(device.has_cfg
                    and (not device.idc_conflict or display_mode == util.CONFIG))
        else:
            # Disable the parent actions
            act_display.setEnabled(False)
            act_write.setEnabled(False)

        for a in self.actions.values():
            if len(a.toolTip()) and not len(a.statusTip()):
                a.setStatusTip(a.toolTip())

        self.actions['toggle_linked_mode'].setText(
                "Views Linked" if self.linked_mode else "Views Unlinked")

    def _tree_node_selected(self, node):
        self.log.debug("_tree_node_selected: %s", node)

        self._previous_tree_node = prev_node = self._selected_tree_node
        self._selected_tree_node = node
        self._selected_device    = node.ref if is_device(node) else None

        self._update_actions()

        hw_signals = [
                'address_conflict_changed',
                'connected',
                'connecting',
                'disconnected',
                'connection_error'
                ]

        mrc_hw_signals = [
                'write_access_changed',
                'silenced_changed'
                ]

        device_signals = [
                'idc_conflict_changed',
                'idc_changed',
                'cfg_idc_changed',
                'hw_idc_changed'
                ]

        device_hw_signals = [
                'rc_changed',
                'address_conflict_changed'
                ]

        app_signals = [
                'hardware_set',
                'config_set'
                ]

        def disconnect_signals(obj, signals):
            self.log.debug("_tree_node_selected: disconnecting '%s' from '%s'", signals, obj)
            for sig in signals:
                try:
                    getattr(obj, sig).disconnect(self._update_actions)
                except TypeError:
                    pass

        def connect_signals(obj, signals):
            self.log.debug("_tree_node_selected: connecting '%s' to '%s'", signals, obj)
            for sig in signals:
                getattr(obj, sig).connect(self._update_actions)

        if prev_node is not None:
            if (is_mrc(prev_node) or is_device(prev_node)) and prev_node.ref.has_hw:
                disconnect_signals(prev_node.ref.hw, hw_signals)

            if (is_mrc(prev_node) and prev_node.ref.has_hw):
                disconnect_signals(prev_node.ref.hw, mrc_hw_signals)

            if is_device(prev_node):
                disconnect_signals(prev_node.ref, device_signals)

            if is_device(prev_node) and prev_node.ref.has_hw:
                disconnect_signals(prev_node.ref.hw, device_hw_signals)

            if isinstance(prev_node.ref, am.AppObject):
                disconnect_signals(prev_node.ref, app_signals)

            mrc = get_mrc(prev_node)

            if mrc is not None and mrc.has_hw:
                disconnect_signals(mrc.hw, mrc_hw_signals)

        if node is not None:
            if (is_mrc(node) or is_device(node)) and node.ref.has_hw:
                connect_signals(node.ref.hw, hw_signals)

            if (is_mrc(node) and node.ref.has_hw):
                connect_signals(node.ref.hw, mrc_hw_signals)

            if is_device(node):
                connect_signals(node.ref, device_signals)

            if is_device(node) and node.ref.has_hw:
                connect_signals(node.ref.hw, device_hw_signals)

            if isinstance(node.ref, am.AppObject):
                connect_signals(node.ref, app_signals)

            mrc = get_mrc(node)

            if mrc is not None and mrc.has_hw:
                connect_signals(mrc.hw, mrc_hw_signals)

        if is_device(node) and not self._show_device_windows(
                node.ref, is_device_cfg(node), is_device_hw(node)):
            # No window for the selected node: make no window active in the mdi area
            self.mainwindow.mdiArea.setActiveSubWindow(None)

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
            assert node.parent is not None
            gui_util.run_add_device_config_dialog(
                    registry=self.app_registry,
                    device_registry=self.context.device_registry,
                    mrc=node.parent.ref,
                    bus=node.bus_number,
                    parent_widget=self.mainwindow)

        if is_device(node):
            gui_util.run_add_device_config_dialog(
                registry=self.app_registry,
                device_registry=self.context.device_registry,
                mrc=node.ref.mrc,
                address=None if node.ref.has_cfg else node.ref.address,
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

        if ((is_mrc(node) or is_device(node)) and
                node.ref.has_cfg):
            self.treeview.cfg_view.edit(
                    self.treeview.cfg_model.index_for_ref(node.ref))

    def _connect_or_disconnect(self):
        node = self._selected_tree_node
        a = self.actions['connect_disconnect']

        if is_registry(node):
            if all((mrc.has_hw and mrc.hw.is_connected()) for mrc in node.ref):
                futures = [mrc.hw.disconnectMrc() for mrc in node.ref]
            else:
                futures = list()
                for mrc in node.ref:
                    if not mrc.has_hw:
                        futures.append(add_mrc_connection(self.app_registry.hw, mrc.url, True))
                    elif not mrc.hw.is_connected() and not mrc.hw.is_connecting():
                        futures.append(mrc.hw.connectMrc())

            if len(futures):
                future.all_done(*futures).add_done_callback(
                        self._update_actions_cb)

        if is_mrc(node):
            if not node.ref.has_hw:
                add_mrc_connection(self.app_registry.hw, node.ref.url, True)
            elif node.ref.hw.is_disconnected() and not node.ref.hw.is_connecting():
                try:
                    node.ref.hw.connectMrc()
                    a.setIcon(a.icons['disconnect'])
                except (IsConnecting, IsConnected):
                    pass
            else:
                node.ref.hw.disconnectMrc()
                a.setIcon(a.icons['connect'])

    def _refresh(self):
        node = self._selected_tree_node

        assert is_hardware(node)

        devices = None

        if is_registry(node):
            devices = [d for mrc in node.ref for d in mrc if d.has_hw]

        elif is_mrc(node):
            devices = [d for d in node.ref if d.has_hw]

        elif is_bus(node):
            devices = [d for d in node.parent.ref.get_devices(bus=node.bus_number) if d.has_hw]

        elif is_device(node):
            devices = [node.ref]

        if not len(devices):
            self.logview.append("Refresh: no devices present")
            return

        gen     = hardware_util.refresh_device_memory(devices)
        runner  = async_util.DefaultGeneratorRunner(gen, self.mainwindow)

        dialog  = config_gui.SubProgressDialog(title="Refreshing device memory")
        dialog.canceled.connect(runner.close)
        runner.progress_changed.connect(dialog.set_progress)

        f  = runner.start()
        fo = future.FutureObserver(f)
        fo.done.connect(dialog.close)
        dialog.exec_()

        if f.done() and f.exception() is not None:
            log.error("Refresh: %s", f.exception())
            QtWidgets.QMessageBox.critical(self.mainwindow, "Error", str(f.exception()))

    def _toggle_rc(self):
        node = self._selected_tree_node

        if is_device(node) and node.ref.has_hw:
            f = node.ref.hw.set_rc(not node.ref.hw.rc)
            f.add_done_callback(self._update_actions_cb)

    def _toggle_write_access(self):
        mrc = get_mrc(self._selected_tree_node).hw

        if not mrc.is_connected():
            return

        f = None

        if mrc.write_access:
            f = mrc.release_write_access()
        else:
            force = False

            if not mrc.can_acquire_write_access():
                answer = QtWidgets.QMessageBox.question(
                        self.mainwindow,
                        "Acquire write access",
                        "Write access is currently taken by another client.\nForcibly acquire write access?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.No)

                if answer != QtWidgets.QMessageBox.Yes:
                    self._update_actions()
                    return

                force = True

            f = mrc.acquire_write_access(force)

        if f is not None:
            f.add_done_callback(self._update_actions_cb)

    def _toggle_silent_mode(self):
        mrc = get_mrc(self._selected_tree_node).hw

        if not mrc.is_connected():
            return

        f = mrc.set_silenced(not mrc.silenced)
        f.add_done_callback(self._update_actions_cb)

    def _add_mrc_connection(self):
        gui_util.run_add_mrc_connection_dialog(
                registry=self.app_registry,
                parent_widget=self.mainwindow)

    def _remove_mrc_connection(self):
        node = self._selected_tree_node

        def do_remove(f_ignored):
            self.app_registry.hw.remove_mrc(node.ref.hw)

        node.ref.hw.disconnectMrc().add_done_callback(do_remove)

    def _view_server_log(self):
        node   = self._selected_tree_node
        mrc    = node.ref.hw
        server = mrc.connection.server
        url    = mrc.connection.url
        view   = gui_util.ServerLogView(server, parent=self.mainwindow)
        sub    = QtWidgets.QMdiSubWindow()
        sub.setWidget(view)
        sub.setAttribute(Qt.WA_DeleteOnClose)
        sub.setWindowIcon(util.make_icon(":/window-icon.png"))
        sub.setWindowTitle("Server log for %s" % url)
        self.mainwindow.mdiArea.addSubWindow(sub)
        sub.show()

    def _open_device_widget(self):
        node = self._selected_tree_node

        self.log.debug("_open_device_widget: node=%s, is_cfg=%s, is_hw=%s",
                node, is_device_cfg(node), is_device_hw(node))

        self._create_device_widget_window(self._selected_device,
                is_device_cfg(node), is_device_hw(node))

    def _open_device_table(self):
        node = self._selected_tree_node

        self.log.debug("_open_device_table: node=%s, is_cfg=%s, is_hw=%s",
                node, is_device_cfg(node), is_device_hw(node))

        self._create_device_table_window(self._selected_device,
                is_device_cfg(node), is_device_hw(node))

    def _check_config(self):
        node = self._selected_tree_node

        if is_registry(node):
            gen = (d for mrc in node.ref for d in mrc)
        elif is_mrc(node):
            gen = (d for d in node.ref)
        elif is_bus(node):
            assert node.parent is not None
            gen = (d for d in node.parent.ref if d.bus == node.bus_number)
        elif is_device(node):
            gen = (d for d in (node.ref,))
        elif node is None:
            gen = (d for mrc in self.app_registry.mrcs for d in mrc)
        else:
            self.log.warning("check config: unsupported node type %s", node)
            return

        predicate = lambda d: not d.idc_conflict and d.has_cfg
        devices   = filter(predicate, gen)

        self.log.info("check config: node=%s, devices=%s", node, devices)

        self.set_linked_mode(True)

        runner = config_gui.ReadConfigParametersRunner(
                devices=devices,
                parent_widget=self.mainwindow)

        progress_dialog = config_gui.SubProgressDialog(title="Reading hardware values")
        runner.progress_changed.connect(progress_dialog.set_progress)
        progress_dialog.canceled.connect(runner.close)
        f = runner.start()
        fo = future.FutureObserver(f)
        fo.done.connect(progress_dialog.close)
        progress_dialog.exec_()

        if f.done() and f.exception() is not None:
            log.error("Check config: %s", f.exception())
            QtWidgets.QMessageBox.critical(self.mainwindow, "Error", str(f.exception()))

    def _run_config_creation_prompt(self, device):
        QMB = QtWidgets.QMessageBox
        mb  = QMB(QMB.Question,
                "Create device config",
                """
Config for %s at (%s, %d, %X) does not exist yet.
Initialize using the current hardware values or the device defaults?
                """ % (device.get_device_name(), device.mrc.get_display_url(), device.bus, device.address),
                buttons=QMB.Yes | QMB.No | QMB.Cancel,
                parent=self.mainwindow)

        mb.button(QMB.Yes).setText("Hardware values")
        mb.button(QMB.No).setText("Device defaults")

        res = mb.exec_()
        d = { QMB.Yes: 'hardware', QMB.No:  'defaults' }
        return d.get(res, False)

    def _run_create_config(self, device):
        source = self._run_config_creation_prompt(device)

        if not source:
            return False

        device.create_config()

        if source == 'hardware':
            progress_dialog = config_gui.SubProgressDialog(title="Copying from hardware to config")
            runner = config_gui.FillDeviceConfigsRunner([device], self.mainwindow)
            progress_dialog.canceled.connect(runner.close)
            f = runner.start()
            fo = future.FutureObserver(f)
            fo.done.connect(progress_dialog.close)
            progress_dialog.exec_()

            if f.done() and f.exception() is not None:
                log.error("Check config: %s", f.exception())
                QtWidgets.QMessageBox.critical(self.mainwindow, "Error", str(f.exception()))

        return True

    def _apply_config_to_hardware(self):
        node = self._selected_tree_node
        devices = None

        if is_setup(node):
            devices = [d for mrc in node.ref for d in mrc if d.has_cfg]

        elif is_mrc(node):
            devices = [d for d in node.ref if d.has_cfg]

        elif is_bus(node):
            devices = [d for d in node.parent.ref.get_devices(bus=node.bus_number) if d.has_cfg]

        elif is_device(node):
            devices = [node.ref]

        if not len(devices):
            return

        runner = config_gui.ApplyDeviceConfigsRunner(
                devices=devices,
                parent_widget=self.mainwindow)
        progress_dialog = config_gui.SubProgressDialog(title="Applying config to hardware")

        runner.progress_changed.connect(progress_dialog.set_progress)
        progress_dialog.canceled.connect(runner.close)
        f = runner.start()
        fo = future.FutureObserver(f)
        fo.done.connect(progress_dialog.close)
        progress_dialog.exec_()

        if f.done() and f.exception() is not None:
            log.error("Apply config: %s", f.exception())
            QtWidgets.QMessageBox.critical(self.mainwindow, "Error", str(f.exception()))

    def _apply_hardware_to_config(self):
        # FIXME: this does not work for MRCs that have never been connected as
        # the device list will be empty which will cause the runners generator
        # to do nothing. Instead of specifying the devices here a list of MRCs
        # could be passed and the list of devices would be built dynamically.

        node = self._selected_tree_node
        devices = None

        if is_registry(node):
            devices = [d for mrc in node.ref for d in mrc if d.has_hw]

        elif is_mrc(node):
            devices = [d for d in node.ref if d.has_hw]

        elif is_bus(node):
            devices = [d for d in node.parent.ref.get_devices(bus=node.bus_number) if d.has_hw]

        elif is_device(node):
            devices = [node.ref]

        assert len(devices)

        runner = config_gui.FillDeviceConfigsRunner(
                devices=devices, parent_widget=self.mainwindow)
        progress_dialog = config_gui.SubProgressDialog(title="Copying from hardware to config")

        runner.progress_changed.connect(progress_dialog.set_progress)
        progress_dialog.canceled.connect(runner.close)
        f = runner.start()
        fo = future.FutureObserver(f)
        fo.done.connect(progress_dialog.close)
        progress_dialog.exec_()

        if f.done() and f.exception() is not None:
            log.error("Fill config: %s", f.exception())
            QtWidgets.QMessageBox.critical(self.mainwindow, "Error", str(f.exception()))

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

    def _edit_mrc_config(self):
        gui_util.run_edit_mrc_config(mrc=self._selected_tree_node.ref,
                registry=self.app_registry, parent_widget=self.mainwindow)

    def _edit_device_config(self):
        gui_util.run_edit_device_config(
                device=self._selected_tree_node.ref,
                registry=self.app_registry,
                device_registry=self.context.device_registry,
                parent_widget=self.mainwindow)

    def quit(self):
        """Non-blocking method to quit the application. Needs a running event
        loop."""
        QtCore.QMetaObject.invokeMethod(self.mainwindow, "close", Qt.QueuedConnection)

    def _on_subwindow_activated(self, window):
        self._current_subwindow = window
        self._update_actions()

        if self._subwindow_toolbar is not None:
            self.mainwindow.removeToolBar(self._subwindow_toolbar)
            self._subwindow_toolbar = None

        if isinstance(window, gui_util.DeviceSubWindow):
            device       = window.device
            display_mode = window.display_mode
            write_mode   = window.write_mode

            self.log.debug("_on_subwindow_activated: d=%s, has_hw=%s, has_cfg=%s, display_mode=%s, write_mode=%s",
                    device, device.has_hw, device.has_cfg,
                    util.RW_MODE_NAMES[display_mode], util.RW_MODE_NAMES[write_mode])

            if display_mode & util.CONFIG:
                self.treeview.select_config_node_by_ref(device)
            elif display_mode & util.HARDWARE:
                self.treeview.select_hardware_node_by_ref(device)

        if hasattr(window, 'has_toolbar') and window.has_toolbar():
            self._subwindow_toolbar = tb = window.get_toolbar()
            tb.setIconSize(GUIApplication.TOOLBAR_ICON_SIZE)
            font = tb.font()
            font.setPixelSize(GUIApplication.TOOLBAR_FONT_SIZE)
            tb.setFont(font)
            tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            tb.setWindowTitle("Subwindow Toolbar")
            tb.setObjectName("subwindow_toolbar")
            self.mainwindow.addToolBar(tb)
            tb.show()

    def active_subwindow(self):
        return self.mainwindow.mdiArea.activeSubWindow()

    # Note: The toggled() signal is emitted on user action _and_ on
    # setChecked() and similar calls. In contrast triggered() is only emitted
    # on user action.
    def _on_display_hw_triggered(self, b):
        if b:
            w = self.active_subwindow()
            w.display_mode = util.HARDWARE
            self._update_actions()

    def _on_display_cfg_triggered(self, b):
        if b:
            w = self.active_subwindow()
            w.display_mode = util.CONFIG
            self._update_actions()

    def _on_display_combined_triggered(self, b):
        if b:
            w = self.active_subwindow()
            w.display_mode = util.COMBINED
            self._update_actions()

    def _on_write_hw_triggered(self, b):
        if b:
            w = self.active_subwindow()
            w.write_mode = util.HARDWARE
            self._update_actions()

    def _on_write_cfg_triggered(self, b):
        if b:
            w = self.active_subwindow()
            w.write_mode = util.CONFIG
            self._update_actions()

    def _on_write_combined_triggered(self, b):
        if b:
            w = self.active_subwindow()
            w.write_mode = util.COMBINED
            self._update_actions()

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

        self.log.debug("Found %d windows for %s", util.ilen(windows), device)

        for subwin in windows:
            if subwin.isMinimized():
                subwin.showNormal()
            self.mainwindow.mdiArea.setActiveSubWindow(subwin)

        return util.ilen(windows) > 0

    def _close_device_windows(self, device):
        for window in copy.copy(self._device_window_map.get(device, set())):
            window.close()

    def _tree_node_activated(self, node):
        if is_device_hw(node) and node.ref.has_hw and node.ref.address_conflict:
            return

        if is_device(node):
            device = node.ref

            self._show_or_create_device_window(device,
                    is_device_cfg(node), is_device_hw(node))

    def _show_or_create_device_window(self, device, from_config_side, from_hw_side):
        self.log.debug("_show_or_create_device_window: device=%s, cfg_side=%s, hw_side=%s",
                device, from_config_side, from_hw_side)

        if self._show_device_windows(device, from_config_side, from_hw_side):
            return

        try:
            module = device.module
        except IDCConflict:
            module = device.cfg_module if from_config_side else device.hw_module

        self.log.debug("_show_or_create_device_window: using module %s", module)

        if module.has_widget_class():
            self._create_device_widget_window(device, from_config_side, from_hw_side)
        else:
            self._create_device_table_window(device, from_config_side, from_hw_side)

    def _create_device_table_window(self, app_device, from_config_side, from_hw_side):
        self.log.debug("_create_device_table_window: device=%s, cfg_side=%s, hw_side=%s, linked_mode=%s",
                app_device, from_config_side, from_hw_side, self.linked_mode)

        if self.linked_mode and not app_device.has_cfg:
            if not self._run_create_config(app_device):
                return

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
        self.log.debug("_create_device_widget_window: device=%s, cfg_side=%s, hw_side=%s, linked_mode=%s",
                app_device, from_config_side, from_hw_side, self.linked_mode)

        if self.linked_mode and not app_device.has_cfg:
            if not self._run_create_config(app_device):
                return

        if self.linked_mode and not app_device.idc_conflict:
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
        self._previous_tree_node = self._selected_tree_node = self._selected_device = None
        self._update_actions()

        for device, window_list in self._device_window_map.items():
            # Use a copy of window_list here as closing windows will modify the
            # original list.
            for window in list(window_list):
                try:
                    if linked_mode and window.has_combined_display() and not device.idc_conflict:
                        window.display_mode = util.COMBINED
                    elif not linked_mode:
                        if util.COMBINED in (window.display_mode, window.write_mode):
                            window.close()

                    window.linked_mode = linked_mode
                except AttributeError:
                    pass

    def get_linked_mode(self):
        return self._linked_mode

    mainwindow      = property(get_mainwindow)
    app_registry    = property(lambda self: self.context.app_registry)
    device_registry = property(lambda self: self.context.device_registry)
    linked_mode     = property(get_linked_mode, set_linked_mode)

    def _hw_mrc_added(self, mrc):
        self.log.debug("hw mrc added: %s", mrc.url)
        mrc.connecting.connect(partial(self._hw_mrc_connecting, mrc=mrc))
        mrc.connected.connect(self._update_actions)
        mrc.disconnected.connect(partial(self._hw_mrc_disconnected, mrc=mrc))

    def _hw_mrc_connecting(self, f, mrc):
        con = mrc.get_controller().connection
        if isinstance(con, mrc_connection.MRCConnection):
            self.logview.append("Connecting to %s" % mrc.get_display_url())

        fo = future.FutureObserver()

        def done(f, fo=fo):
            try:
                f.result()
                con = mrc.get_controller().connection
                if isinstance(con, mrc_connection.MRCConnection):
                    self.logview.append("Connected to %s" % mrc.get_display_url())
            except Exception as e:
                self.logview.append("Error connecting to %s: %s" % (mrc.get_display_url(), e))

            fo.deleteLater()
            self._update_actions()

        def progress_text_changed(txt):
            self.logview.append("%s: %s" % (mrc.get_display_url(), txt))

        f.add_done_callback(done)
        fo.set_future(f)
        fo.progress_text_changed.connect(progress_text_changed)

    def _hw_mrc_disconnected(self, mrc):
        con = mrc.get_controller().connection
        if isinstance(con, mrc_connection.MRCConnection):
            self.logview.append("Disconnected from %s" % mrc.get_display_url())
        self._update_actions()

    # Device table window creation
    def _add_device_table_window(self, device, display_mode, write_mode):
        self.log.debug("Adding device table for %s with display_mode=%s, write_mode=%s",
                device,
                util.RW_MODE_NAMES[display_mode],
                util.RW_MODE_NAMES[write_mode])

        widget = device_tableview.DeviceTableWidget(device, display_mode, write_mode)
        subwin = gui_util.DeviceTableSubWindow(widget=widget)
        subwin.set_linked_mode(self.linked_mode)

        return self._register_device_subwindow(subwin)

    def _add_device_widget_window(self, app_device, display_mode, write_mode):
        self.log.debug("Adding device widget for %s with display_mode=%s, write_mode=%s",
                app_device,
                util.RW_MODE_NAMES[display_mode],
                util.RW_MODE_NAMES[write_mode])

        widget = app_device.make_device_widget(display_mode, write_mode,
                make_settings=self.context.make_qsettings)

        subwin = gui_util.DeviceWidgetSubWindow(widget=widget)
        subwin.set_linked_mode(self.linked_mode)

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
        menu = QtWidgets.QMenu()

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
            menu.addSeparator()
            add_action(self.actions['edit_mrc_config'])

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
            if self.actions['add_config'].isEnabled():
                add_action(self.actions['add_config'])
            #add_action(self.actions['show_device_extensions'])
            menu.addSeparator()
            add_action(self.actions['edit_device_config'])

        if not menu.isEmpty():
            menu.exec_(view.mapToGlobal(pos))

    def _hw_context_menu(self, node, idx, pos, view):
        menu = QtWidgets.QMenu()

        def add_action(action):
            if action.isEnabled():
                menu.addAction(action)

        if is_registry(node):
            add_action(self.actions['add_mrc_connection'])
            add_action(self.actions['refresh'])

        if is_mrc(node):
            add_action(self.actions['connect_disconnect'])
            add_action(self.actions['refresh'])
            menu.addSeparator()

            mrc = node.ref
            if mrc.hw is not None and hasattr(mrc.hw.connection, 'server'):
                add_action(self.actions['view_server_log'])

            add_action(self.actions['remove_mrc_connection'])

        if is_bus(node):
            add_action(self.actions['refresh'])

        if is_device(node):
            add_action(self.actions['open_device_widget'])
            add_action(self.actions['open_device_table'])
            add_action(self.actions['toggle_rc'])
            add_action(self.actions['refresh'])
            #add_action(self.actions['show_device_extensions'])

        if not menu.isEmpty():
            menu.exec_(view.mapToGlobal(pos))

    def eventFilter(self, watched_object, event):
        if (event.type() == QtCore.QEvent.Close
                and isinstance(watched_object, QtWidgets.QMdiSubWindow)):

            self.log.debug("CloseEvent for %s", watched_object)

            if self._current_subwindow is watched_object:
                self._current_subwindow = None

            gui_util.store_subwindow_state(watched_object, self.context.make_qsettings())

            if (hasattr(watched_object, 'device')
                    and watched_object.device in self._device_window_map):
                # Remove the subwindow from the set of device windows
                self.log.debug("removing subwin %s for device %s", watched_object, watched_object.device)
                self._device_window_map[watched_object.device].remove(watched_object)

        elif (event.type() == QtCore.QEvent.Close
                and watched_object is self.mainwindow):
            self.log.debug("CloseEvent for mainwindow")
            if not gui_util.run_close_setup(self.context, self.mainwindow):
                event.ignore()
                return True

        return False

    def _show_device_extensions(self):
        node = self._selected_tree_node
        self._create_device_extension_window(
                self._selected_device,
                is_device_cfg(node),
                is_device_hw(node))

    def _create_device_extension_window(self, app_device, from_config_side, from_hw_side):
        from pyqtgraph import parametertree as pt
        tree = widget = pt.ParameterTree()
        subwin = QtWidgets.QMdiSubWindow()
        subwin.setWidget(widget)
        self.mainwindow.mdiArea.addSubWindow(subwin)
        subwin.show()

        device = app_device.cfg if from_config_side else app_device.hw
        profile = app_device.cfg_profile if from_config_side else app_device.hw_profile
        extensions = device.get_extensions()
        print("extensions:", extensions)
        extensions_param = extensions_to_ptree(extensions, profile)
        extensions_param.sigTreeStateChanged.connect(on_tree_state_changed)
        tree.setParameters(extensions_param, showTop=False)

    def _show_quickstart(self):
        subwin = self.mainwindow.findChild(QtWidgets.QMdiSubWindow, "quickstart")

        if subwin:
            subwin.widget().show()
            subwin.raise_()
            subwin.showNormal()
            return

        subwin = QtWidgets.QMdiSubWindow()
        subwin.setWidget(gui_tutorial.TutorialWidget(self))
        subwin.setWindowTitle("Quickstart")
        subwin.setObjectName("quickstart")
        subwin.setWindowIcon(util.make_icon(":/window-icon.png"))
        subwin.resize(QtCore.QSize(600, 400))
        self.mainwindow.mdiArea.addSubWindow(subwin)
        subwin.show()

def on_tree_state_changed(emitting_param, changes):
    print("on_tree_state_changed")
    print("changes:", changes)

    for param, change, value in changes:
        print(param)
        print(change)
        print(value)
        print(emitting_param.childPath(param))
        print("=" * 15)

def extensions_to_ptree(extensions, device_profile):
    from pyqtgraph import parametertree as pt

    def list2param(name, value):
        ret = pt.Parameter.create(name=name, type='group')
        ret.type = type(list())
        for idx, val in enumerate(value):
            ret.addChild(value2param(name=str(idx), value=val))
        return ret

    def dict2param(name, value):
        ret = pt.Parameter.create(name=name, type='group')
        ret.type = type(dict())
        for k, v in value.items():
            ret.addChild(value2param(name=str(k), value=v))
        return ret

    def value2param(name, value):
        log = logging.getLogger(__name__)
        log.warning("value2param n=%s, v=%s", name, value)
        try:
            ext_profile = device_profile.get_extension(name)
            log.warning("ext_profile from device_profile")
        except KeyError:
            ext_profile = dict(name=name)
            log.warning("ext_profile from dict")

        log.warning("ext_profile=%s", ext_profile)
        print(ext_profile)

        #if 'values' in ext_profile:
        #    log.warning(value)
        #    log.warning(ext_profile)
        #    return pt.Parameter.create(value=value, type='list', **ext_profile)
        if isinstance(value, str):
            log.warning("str")
            return pt.Parameter.create(type='str', **ext_profile)
        elif isinstance(value, int):
            log.warning("int")
            return pt.Parameter.create(type='int', **ext_profile)
        elif isinstance(value, float):
            log.warning("float")
            return pt.Parameter.create(type='float', **ext_profile)
        elif isinstance(value, list):
            log.warning("list2param %s=%s", name, value)
            return list2param(name, value)
        elif isinstance(value, dict):
            log.warning("dict2param %s=%s", name, value)
            return dict2param(name, value)
        else:
            raise TypeError("value2xml: unhandled value type '%s'" % type(value).__name__)

    ret = pt.Parameter.create(name='root', type='group')
    ret.sigTreeStateChanged.connect(on_tree_state_changed)

    log.warning("value2param: exts=%s %s", type(extensions), extensions)
    for name, value in extensions.items():
        log.warning("value2param iteration: n=%s, v=%s", name, value)
        param = value2param(name, value)
        ret.addChild(param)

    return ret
