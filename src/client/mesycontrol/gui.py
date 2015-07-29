#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
import collections
import copy
import logging
import os
import sys
import weakref

import pyqtgraph.console
pg = pyqtgraph

from qt import pyqtSlot
from qt import Qt
from qt import QtCore
from qt import QtGui

from mc_treeview import MCTreeView
from model_util import add_mrc_connection
from ui.dialogs import AddDeviceDialog
from ui.dialogs import AddMRCDialog
from util import make_icon
from util import make_standard_icon
import basic_model as bm
import config_gui
import config_model as cm
import config_tree_model as ctm
import config_xml
import device_tableview
import future
import gui_util
import hardware_tree_model as htm
import log_view
import resources
import util

log = logging.getLogger(__name__)

# TODO: enable/disable display actions on hw/cfg state change (disconnect, closed, ...)

# ===== MRC =====
def run_add_mrc_config_dialog(registry, parent_widget=None):
    urls_in_use = [mrc.url for mrc in registry.cfg.get_mrcs()]
    serial_ports = util.list_serial_ports()
    dialog = AddMRCDialog(serial_ports=serial_ports,
            urls_in_use=urls_in_use, parent=parent_widget)
    dialog.setModal(True)

    def accepted():
        url, connect = dialog.result()
        mrc = cm.MRC(url)
        registry.cfg.add_mrc(mrc)

        if connect:
            mrc = registry.hw.get_mrc(url)
            if not mrc:
                add_mrc_connection(registry.hw, url, True)
            elif mrc.is_disconnected():
                mrc.connect()

    dialog.accepted.connect(accepted)
    dialog.show()

def run_add_mrc_connection_dialog(registry, parent_widget=None):
    urls_in_use = [mrc.url for mrc in registry.hw.get_mrcs()]
    serial_ports = util.list_serial_ports()
    dialog = AddMRCDialog(serial_ports=serial_ports, urls_in_use=urls_in_use,
            do_connect_default=True, parent=parent_widget)
    dialog.setModal(True)

    def accepted():
        try:
            url, connect = dialog.result()
            add_mrc_connection(registry.hw, url, connect)
        except Exception as e:
            log.exception("run_add_mrc_connection_dialog")
            QtGui.QMessageBox.critical(parent_widget, "Error", str(e))

    dialog.accepted.connect(accepted)
    dialog.show()

# ===== Device =====
def run_add_device_config_dialog(device_registry, registry, mrc, bus=None, parent_widget=None):
    try:
        aa = [(b, d) for b in bm.BUS_RANGE for d in bm.DEV_RANGE
                if not mrc.cfg or not mrc.cfg.get_device(b, d)]

        dialog = AddDeviceDialog(bus=bus, available_addresses=aa,
                known_idcs=device_registry.get_device_names(), parent=parent_widget)
        dialog.setModal(True)

        def accepted():
            bus, address, idc, name = dialog.result()
            device_config = cm.make_device_config(bus, address, idc, name, device_registry.get_device_profile(idc))
            if not mrc.has_cfg:
                registry.cfg.add_mrc(cm.MRC(mrc.url))
            mrc.cfg.add_device(device_config)

        dialog.accepted.connect(accepted)
        dialog.show()
    except RuntimeError as e:
        log.exception(e)
        QtGui.QMessageBox.critical(parent_widget, "Error", str(e))

def run_load_device_config(device, context, parent_widget):
    directory_hint = os.path.dirname(str(context.make_qsettings().value(
            'Files/last_config_file', QtCore.QString()).toString()))

    filename = str(QtGui.QFileDialog.getOpenFileName(parent_widget, "Load Device config",
        directory=directory_hint, filter="XML files (*.xml);;"))

    if not len(filename):
        return False

    try:
        # FIXME: it would nice to just having to call device.cfg = config. This
        # would also keep the app_model alive in case there's no hardware
        # present.
        config = config_xml.read_device_config(filename)
        config.bus = device.bus
        config.address = device.address
        mrc = device.mrc.cfg
        mrc.remove_device(device.cfg)
        mrc.add_device(config)
        context.make_qsettings().setValue('Files/last_config_file', filename)
        return True
    except Exception as e:
        log.exception(e)
        QtGui.QMessageBox.critical(parent_widget, "Error",
                "Loading device config from %s failed:\n%s" % (filename, e))
        return False

def run_save_device_config(device, context, parent_widget):
    directory_hint = os.path.dirname(str(context.make_qsettings().value(
            'Files/last_config_file', QtCore.QString()).toString()))

    filename = str(QtGui.QFileDialog.getSaveFileName(parent_widget, "Save Device config as",
        directory=directory_hint, filter="XML files (*.xml);;"))

    if not len(filename):
        return False

    root, ext = os.path.splitext(filename)

    if not len(ext):
        filename += ".xml"

    try:
        config_xml.write_device_config(device_config=device.cfg, dest=filename,
                parameter_names=context.device_registry.get_parameter_names(device.cfg.idc))
        context.make_qsettings().setValue('Files/last_config_file', filename)
        return True
    except Exception as e:
        log.exception(e)
        QtGui.QMessageBox.critical(parent_widget, "Error",
                "Saving device config to %s failed:\n%s" % (filename, e))
        return False

# ===== Setup =====
def run_save_setup(context, parent_widget):
    setup = context.setup

    if not len(setup.filename):
        return run_save_setup_as_dialog(context, parent_widget)

    try:
        config_xml.write_setup(setup=setup, dest=setup.filename,
                idc_to_parameter_names=context.device_registry.get_parameter_name_mapping())

        setup.modified = False
        return True
    except Exception as e:
        log.exception(e)
        QtGui.QMessageBox.critical(parent_widget, "Error", "Saving setup %s failed:\n%s" % (setup.filename, e))
        return False

def run_save_setup_as_dialog(context, parent_widget):
    setup = context.app_registry.cfg

    if len(setup.filename):
        directory_hint = setup.filename
    else:
        directory_hint = os.path.dirname(str(context.make_qsettings().value(
                'Files/last_setup_file', QtCore.QString()).toString()))

    filename = str(QtGui.QFileDialog.getSaveFileName(parent_widget, "Save setup as",
            directory=directory_hint, filter="XML files (*.xml);; *"))

    if not len(filename):
        return False

    root, ext = os.path.splitext(filename)

    if not len(ext):
        filename += ".xml"

    try:
        config_xml.write_setup(setup=setup, dest=filename,
                idc_to_parameter_names=context.device_registry.get_parameter_name_mapping())

        setup.filename = filename
        setup.modified = False
        context.make_qsettings().setValue('Files/last_setup_file', filename)
        return True
    except Exception as e:
        log.exception(e)
        QtGui.QMessageBox.critical(parent_widget, "Error", "Saving setup %s failed:\n%s" % (setup.filename, e))
        return False
    
def run_open_setup_dialog(context, parent_widget):
    if context.setup.modified and len(context.setup):
        do_save = QtGui.QMessageBox.question(parent_widget,
                "Setup modified",
                "The current setup is modified. Do you want to save it?",
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
                QtGui.QMessageBox.Yes)
        if do_save == QtGui.QMessageBox.Yes:
            if not run_save_setup_as_dialog(context, parent_widget):
                return False

    directory_hint = os.path.dirname(str(context.make_qsettings().value(
            'Files/last_setup_file', QtCore.QString()).toString()))

    filename = QtGui.QFileDialog.getOpenFileName(parent_widget, "Open setup file",
            directory=directory_hint, filter="XML files (*.xml);; *")

    if not len(filename):
        return False

    try:
        context.open_setup(filename)
    except Exception as e:
        log.exception(e)
        QtGui.QMessageBox.critical(parent_widget, "Error", "Opening setup file %s failed:\n%s" % (filename, e))
        return False

def run_close_setup(context, parent_widget):
    if context.setup.modified and len(context.setup):
        do_save = QtGui.QMessageBox.question(parent_widget,
                "Setup modified",
                "The current setup is modified. Do you want to save it?",
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
                QtGui.QMessageBox.Yes)
        if do_save == QtGui.QMessageBox.Yes:
            run_save_setup_as_dialog(context, parent_widget)

    context.reset_setup()

def is_setup(node):
    return isinstance(node, (ctm.SetupNode, htm.RegistryNode))

def is_registry(node):
    return is_setup(node)

def is_mrc(node):
    return isinstance(node, (ctm.MRCNode, htm.MRCNode))

def is_bus(node):
    return isinstance(node, (ctm.BusNode, htm.BusNode))

def is_device(node):
    return isinstance(node, (ctm.DeviceNode, htm.DeviceNode))

def is_device_cfg(node):
    return isinstance(node, ctm.DeviceNode)

def is_device_hw(node):
    return isinstance(node, htm.DeviceNode)

class GUIApplication(QtCore.QObject):
    """GUI logic"""
    def __init__(self, context, mainwindow):
        super(GUIApplication, self).__init__()
        self.log            = util.make_logging_source_adapter(__name__, self)
        self._mainwindow    = weakref.ref(mainwindow)
        self.context        = context
        self._linked_mode   = False
        self._device_window_map = dict() # app_model.Device -> list of QMdiSubWindow
        self._selected_tree_node = None  # The currently selected tree node
        self._selected_device = None

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
        self._tree_node_selected(None)

    def _setup_changed(self, app_registry, old, new):
        if old:
            old.modified_changed.disconnect(self._setup_modified_changed)

        if new:
            new.modified_changed.connect(self._setup_modified_changed)
            self._setup_modified_changed(new.modified)

    def _setup_modified_changed(self, modified):
        self.actions['save_setup'].setEnabled(modified)

    def _create_actions(self):
        self.actions = collections.OrderedDict()

        # Open setup
        action = QtGui.QAction(make_icon(":/open-setup.png"),
                "&Open setup", self, triggered=self._open_setup)

        action.setToolTip("Open a setup file")
        action.setStatusTip(action.toolTip())
        action.setShortcut(QtGui.QKeySequence.Open)
        action.toolbar = True
        self.actions['open_setup'] = action

        # Save setup
        action = QtGui.QAction(make_icon(":/save-setup.png"),
                "&Save setup", self, triggered=self._save_setup)

        action.setToolTip("Save setup")
        action.setStatusTip(action.toolTip())
        action.setShortcut(QtGui.QKeySequence.Save)
        action.toolbar = True
        self.actions['save_setup'] = action

        # Save setup as
        action = QtGui.QAction(make_icon(":/save-setup-as.png"),
                "S&ave setup as", self, triggered=self._save_setup_as)

        action.setToolTip("Save setup as")
        action.setStatusTip(action.toolTip())
        action.setShortcut(QtGui.QKeySequence.SaveAs)
        action.toolbar = True
        self.actions['save_setup_as'] = action

        # Close setup
        action = QtGui.QAction(make_standard_icon(QtGui.QStyle.SP_DialogCloseButton),
                "Close setup", self, triggered=self._close_setup)

        action.setToolTip("&Close setup")
        action.setStatusTip(action.toolTip())
        action.setShortcut(QtGui.QKeySequence.Close)
        action.toolbar = True
        self.actions['close_setup'] = action

        # Separator
        action = QtGui.QAction(self)
        action.setSeparator(True)
        action.toolbar = True
        self.actions['sep1'] = action

        # Widget window
        action = QtGui.QAction(make_icon(":/open-device-widget.png"),
                "Open device widget", self, triggered=self._open_device_widget)

        action.setToolTip("Open device widget")
        action.setStatusTip(action.toolTip())
        action.toolbar = True
        self.actions['open_device_widget'] = action

        # Table window
        action = QtGui.QAction(make_icon(":/open-device-table.png"),
                "Open device table", self, triggered=self._open_device_table)

        action.setToolTip("Open device table")
        action.setStatusTip(action.toolTip())
        action.toolbar = True
        self.actions['open_device_table'] = action

        # Separator
        action = QtGui.QAction(self)
        action.setSeparator(True)
        action.toolbar = True
        self.actions['sep2'] = action

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
        action.treeview_splitter = True
        self.actions['toggle_linked_mode'] = action

        # Config to Hardware
        action = QtGui.QAction(make_icon(":/apply-config-to-hardware.png"),
                "Apply config to hardware", self, triggered=self._apply_config_to_hardware)
        action.treeview_splitter = True
        self.actions['apply_config_to_hardware'] = action

        # Hardware to Config
        action = QtGui.QAction(make_icon(":/apply-hardware-to-config.png"),
                "Copy hardware values to config", self, triggered=self._apply_hardware_to_config)
        action.treeview_splitter = True
        self.actions['apply_hardware_to_config'] = action

        # Connect
        action = QtGui.QAction(make_icon(":/connect.png"), "&Connect", self)

        # Disconnect
        action = QtGui.QAction(make_icon(":/disconnect.png"), "&Disconnect", self)

        # Refresh
        action = QtGui.QAction(make_icon(":/refresh.png"), "&Refresh", self)

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
        f  = lambda a: hasattr(a, 'toolbar') and a.toolbar

        for action in filter(f, self.actions.values()):
            tb.addAction(action)
            if action.menu() is not None:
                tb.widgetForAction(action).setPopupMode(QtGui.QToolButton.InstantPopup)

    def _populate_treeview(self):
        tvs = self.treeview.splitter_buttons
        f   = lambda a: hasattr(a, 'treeview_splitter') and a.treeview_splitter

        for action in filter(f, self.actions.values()):
            tvs.addAction(action)

    # ===== Action implementations =====
    def _open_setup(self):
        run_open_setup_dialog(context=self.context, parent_widget=self.mainwindow)

    def _save_setup(self):
        run_save_setup(context=self.context, parent_widget=self.mainwindow)

    def _save_setup_as(self):
        run_save_setup_as_dialog(context=self.context, parent_widget=self.mainwindow)

    def _close_setup(self):
        run_close_setup(context=self.context, parent_widget=self.mainwindow)
        self.context.make_qsettings().remove('Files/last_setup_file')

    def _open_device_widget(self):
        node = self._selected_tree_node

        self._create_device_widget_window(self._selected_device,
                is_device_cfg(node), is_device_hw(node))

    def _open_device_table(self):
        node = self._selected_tree_node

        self._create_device_table_window(self._selected_device,
                is_device_cfg(node), is_device_hw(node))

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

    def quit(self):
        """Non-blocking method to quit the application. Needs a running event
        loop."""
        QtCore.QMetaObject.invokeMethod(self.mainwindow, "close", Qt.QueuedConnection)

    def _on_subwindow_activated(self, window):
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

    def _tree_node_selected(self, node):
        self._selected_tree_node = node
        self._selected_device = device = node.ref if is_device(node) else None

        self.actions['open_device_widget'].setEnabled(is_device(node) and device.has_widget_class())
        self.actions['open_device_table'].setEnabled(is_device(node))

        a = self.actions['apply_config_to_hardware']
        a.setEnabled(self.linked_mode and (
            (is_setup(node) and node.ref.has_cfg) or
            (is_mrc(node) and node.ref.has_cfg) or
            (is_bus(node) and node.parent.ref.has_cfg) or
            (is_device(node) and node.ref.has_cfg)))

        a = self.actions['apply_hardware_to_config']
        a.setEnabled(
            (is_setup(node) and node.ref.has_hw) or
            (is_mrc(node) and node.ref.has_hw) or
            (is_bus(node) and node.parent.ref.has_hw) or
            (is_device(node) and node.ref.has_hw))

        if is_device(node) and not self._show_device_windows(device,
                is_device_cfg(node), is_device_hw(node)):
            # No window for the selected node: make no window active in the mdi area
            self.mainwindow.mdiArea.setActiveSubWindow(None)

    def _show_or_create_device_window(self, device, from_config_side, from_hw_side):
        if self._show_device_windows(device, from_config_side, from_hw_side):
            return

        if device.has_widget_class():
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
        if self.linked_mode and app_device.has_hw and app_device.has_cfg:
            write_mode = util.COMBINED
        else:
            write_mode = util.CONFIG if from_config_side else util.HARDWARE

        read_mode = util.CONFIG if from_config_side else util.HARDWARE

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
        restore_subwindow_state(subwin, self.context.make_qsettings())
        subwin.show()
        self._device_window_map.setdefault(subwin.device, set()).add(subwin)
        return subwin

    def _cfg_context_menu(self, node, idx, pos, view):
        menu = QtGui.QMenu()

        if isinstance(node, ctm.SetupNode):
            setup = node.ref.cfg

            menu.addAction("Open Setup").triggered.connect(partial(run_open_setup_dialog,
                context=self.context, parent_widget=self.treeview))

            if len(setup):
                if self.linked_mode:
                    def apply_setup():
                        runner = config_gui.ApplySetupRunner(
                                app_registry=node.ref,
                                device_registry=self.context.device_registry,
                                parent_widget=self.treeview)

                        pd = config_gui.SubProgressDialog()

                        runner.progress_changed.connect(pd.set_progress)
                        pd.canceled.connect(runner.close)

                        f = runner.start()
                        fo = future.FutureObserver(f)
                        fo.done.connect(pd.close)

                        pd.exec_()

                        if f.done() and f.exception() is not None:
                            log.error("apply_setup: %s", f.exception())
                            QtGui.QMessageBox.critical(view, "Error", str(f.exception()))

                    menu.addAction("Apply setup").triggered.connect(apply_setup)

                if len(setup.filename):
                    menu.addAction("Save Setup").triggered.connect(partial(run_save_setup,
                        context=self.context, parent_widget=self.treeview))

                menu.addAction("Save Setup As").triggered.connect(partial(run_save_setup_as_dialog,
                    context=self.context, parent_widget=self.treeview))

                menu.addAction("Close Setup").triggered.connect(partial(run_close_setup,
                    context=self.context, parent_widget=self.treeview))

            menu.addSeparator()

            menu.addAction("Add MRC").triggered.connect(partial(run_add_mrc_config_dialog,
                registry=self.app_registry, parent_widget=self.treeview))

        if isinstance(node, ctm.MRCNode):
            menu.addAction("Add Device").triggered.connect(partial(run_add_device_config_dialog,
                device_registry=self.context.device_registry, registry=self.app_registry,
                mrc=node.ref, parent_widget=self.treeview))

            def remove_mrc():
                self.app_registry.cfg.remove_mrc(node.ref.cfg)

            menu.addAction("Remove MRC").triggered.connect(remove_mrc)

        if isinstance(node, ctm.BusNode):
            menu.addAction("Add Device").triggered.connect(partial(run_add_device_config_dialog,
                device_registry=self.context.device_registry, registry=self.app_registry,
                mrc=node.parent.ref, bus=node.bus_number, 
                parent_widget=self.treeview))

        if isinstance(node, ctm.DeviceNode):
            device = node.ref

            menu.addAction("Open").triggered.connect(
                    partial(self._show_or_create_device_window,
                        device=device, from_config_side=True, from_hw_side=False))

            if device.has_widget_class():
                menu.addAction("Open Widget").triggered.connect(partial(
                    self._create_device_widget_window, app_device=device,
                    from_config_side=True, from_hw_side=False))

            def load_device_config():
                app_device = device
                app_mrc    = app_device.mrc

                if run_load_device_config(device=device, context=self.context,
                        parent_widget=self.treeview):
                    # A config was loaded. If the app_device did not have a
                    # hardware model it will have been removed from the app_mrc
                    # as a result of calling remove_device() on the config mrc.
                    # Afterwards a new app_model.Device will have been created
                    # by calling add_device() on the config mrc. Query the app
                    # mrc to get the newly created app device.
                    app_device = app_mrc.get_device(app_device.bus, app_device.address)

                    # Select the hardware node before the config node to end up
                    # with focus in the config tree.
                    if self.linked_mode and not app_device.idc_conflict:
                        self.treeview.select_hardware_node_by_ref(app_device)

                    self.treeview.select_config_node_by_ref(app_device)

            menu.addAction("Load From File").triggered.connect(load_device_config)

            menu.addAction("Save To File").triggered.connect(
                    partial(run_save_device_config,
                        device=device,
                        context=self.context,
                        parent_widget=self.treeview))

            if (self.linked_mode and device.has_cfg and device.has_hw
                    and device.mrc.hw.is_connected()):

                def apply_config():
                    runner = config_gui.ApplyDeviceConfigRunner(
                            device=device, parent_widget=self.treeview)
                    f  = runner.start()
                    fo = future.FutureObserver(f)
                    pd = QtGui.QProgressDialog()

                    fo.progress_range_changed.connect(pd.setRange)
                    fo.progress_changed.connect(pd.setValue)
                    fo.progress_text_changed.connect(pd.setLabelText)
                    fo.done.connect(pd.close)
                    pd.exec_()
                    if pd.wasCanceled():
                        runner.close()

                    elif f.exception() is not None:
                        log.error("apply_config: %s", f.exception())
                        QtGui.QMessageBox.critical(view, "Error", str(f.exception()))

                menu.addAction("Apply config").triggered.connect(apply_config)

            def remove_device():
                self._close_device_windows(device)
                device.mrc.cfg.remove_device(device.cfg)

            menu.addAction("Remove Device from Setup").triggered.connect(remove_device)

        if not menu.isEmpty():
            menu.exec_(view.mapToGlobal(pos))


    def _hw_context_menu(self, node, idx, pos, view):
        menu = QtGui.QMenu()

        if isinstance(node, htm.RegistryNode):
            menu.addAction("Add MRC Connection").triggered.connect(partial(run_add_mrc_connection_dialog,
                registry=self.app_registry, parent_widget=self.treeview))

        if isinstance(node, htm.MRCNode):
            mrc = node.ref

            if not mrc.hw or mrc.hw.is_disconnected():
                def do_connect():
                    if not mrc.hw:
                        add_mrc_connection(self.app_registry.hw, mrc.url, True)
                    else:
                        mrc.hw.connect()

                menu.addAction("Connect").triggered.connect(do_connect)

            if mrc.hw and mrc.hw.is_connected():
                def do_scanbus():
                    for i in bm.BUS_RANGE:
                        mrc.hw.scanbus(i)
                menu.addAction("Scanbus").triggered.connect(do_scanbus)

            if mrc.hw and (mrc.hw.is_connected() or mrc.hw.is_connecting()):
                menu.addAction("Disconnect").triggered.connect(mrc.hw.disconnect)

            if mrc.hw:
                def do_disconnect():
                    mrc.hw.disconnect().add_done_callback(do_remove)

                def do_remove(f):
                    self.app_registry.hw.remove_mrc(mrc.hw)

                menu.addAction("Remove MRC Connection").triggered.connect(do_disconnect)

        if isinstance(node, htm.BusNode):
            mrc = node.parent.ref
            bus = node.bus_number

            if mrc.hw and mrc.hw.is_connected():
                menu.addAction("Scanbus").triggered.connect(partial(mrc.hw.scanbus, bus))

        if isinstance(node, htm.DeviceNode):
            device = node.ref

            if self.linked_mode or device.has_hw:
                menu.addAction("Open").triggered.connect(
                        partial(self._show_or_create_device_window,
                            device=device, from_config_side=False, from_hw_side=True))

            if device.has_hw:
                if device.has_widget_class():
                    menu.addAction("Open Widget").triggered.connect(partial(
                        self._create_device_widget_window, app_device=device,
                        from_config_side=False, from_hw_side=True))


                def toggle_polling():
                    device.hw.polling = not device.hw.polling

                menu.addAction("Disable polling" if device.hw.polling else "Enable polling"
                        ).triggered.connect(toggle_polling)

        if not menu.isEmpty():
            menu.exec_(view.mapToGlobal(pos))

    def eventFilter(self, watched_object, event):
        if (event.type() == QtCore.QEvent.Close
                and isinstance(watched_object, QtGui.QMdiSubWindow)):

            store_subwindow_state(watched_object, self.context.make_qsettings())

            if (hasattr(watched_object, 'device')
                    and watched_object.device in self._device_window_map):
                # Remove the subwindow from the set of device windows
                self.log.debug("removing subwin %s for device %s", watched_object, watched_object.device)
                self._device_window_map[watched_object.device].remove(watched_object)

        elif (event.type() == QtCore.QEvent.Close
                and watched_object is self.mainwindow):
            run_close_setup(self.context, self.mainwindow)

        return False

def store_subwindow_state(subwin, settings):
    name = str(subwin.objectName())

    if not len(name):
        return False

    settings.beginGroup("MdiSubWindows")
    try:
        settings.setValue(name + "_size", subwin.size())
        settings.setValue(name + "_pos",  subwin.pos())
        return True
    finally:
        settings.endGroup()

def restore_subwindow_state(subwin, settings):
    name = str(subwin.objectName())

    if not len(name):
        return False

    settings.beginGroup("MdiSubWindows")
    try:
        if settings.contains(name + "_size"):
            subwin.resize(settings.value(name + "_size").toSize())

        if settings.contains(name + "_pos"):
            subwin.move(settings.value(name + "_pos").toPoint())

        return True
    finally:
        settings.endGroup()

class MainWindow(QtGui.QMainWindow):
    def __init__(self, context, parent=None):
        super(MainWindow, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.context = context
        util.loadUi(":/ui/mainwin.ui", self)

        # Treeview
        self.treeview = MCTreeView(app_registry=context.app_registry,
                device_registry=context.device_registry)

        dw_tree = QtGui.QDockWidget("Device tree", self)
        dw_tree.setObjectName("dw_treeview")
        dw_tree.setWidget(self.treeview)
        dw_tree.setFeatures(QtGui.QDockWidget.DockWidgetMovable | QtGui.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dw_tree)

        # Log view
        self.logview = log_view.LogView(parent=self)
        dw_logview = QtGui.QDockWidget("Application Log", self)
        dw_logview.setObjectName("dw_logview")
        dw_logview.setWidget(self.logview)
        dw_logview.setFeatures(QtGui.QDockWidget.DockWidgetMovable | QtGui.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dw_logview)

        self.restore_settings()

    def store_settings(self):
        settings = self.context.make_qsettings()

        settings.beginGroup("MainWindow")

        try:
            settings.setValue("size",       self.size());
            settings.setValue("pos",        self.pos());
            settings.setValue("geometry",   self.saveGeometry());
            settings.setValue("state",      self.saveState());
        finally:
            settings.endGroup()

        window_list = self.mdiArea.subWindowList()

        for window in window_list:
            store_subwindow_state(window, settings)

    def restore_settings(self):
        settings = self.context.make_qsettings()

        settings.beginGroup("MainWindow")
        try:
            self.resize(settings.value("size", QtCore.QSize(1024, 768)).toSize())
            self.move(settings.value("pos", QtCore.QPoint(0, 0)).toPoint())
            self.restoreGeometry(settings.value("geometry").toByteArray())
            self.restoreState(settings.value("state").toByteArray())
        finally:
            settings.endGroup()

    @pyqtSlot()
    def on_actionAbout_triggered(self):
        # TODO: add icon, text and version number
        dialog = QtGui.QMessageBox(self)
        dialog.setWindowTitle("About mesycontrol")
        dialog.setStandardButtons(QtGui.QMessageBox.Ok)
        dialog.exec_()

    @pyqtSlot()
    def on_actionAbout_Qt_triggered(self):
        QtGui.QApplication.instance().aboutQt()

    def closeEvent(self, event):
        self.store_settings()
        super(MainWindow, self).closeEvent(event)
