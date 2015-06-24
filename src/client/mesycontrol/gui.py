#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from functools import partial
import logging
import os
import weakref
import sys

import pyqtgraph.console
pg = pyqtgraph

from qt import pyqtSlot
from qt import Qt
from qt import QtCore
from qt import QtGui
from qt import uic

from mc_treeview import MCTreeView
from ui.dialogs import AddDeviceDialog
from ui.dialogs import AddMRCDialog
import basic_model as bm
import config_model as cm
import config_tree_model as ctm
import config_xml
import device_tableview
import hardware_controller
import hardware_model as hm
import hardware_tree_model as htm
import log_view
import mrc_connection
import util

log = logging.getLogger('gui')

def add_mrc_connection(registry, url, do_connect):
    """Adds an MRC connection using the given url to the application registry.
    If `do_connect' is True this function will start a connection attempt and
    return the corresponding Future object. Otherwise the newly added MRC will
    be in disconnected state and None is returned."""

    connection      = mrc_connection.factory(url=url)
    controller      = hardware_controller.Controller(connection)
    mrc             = hm.MRC(url)
    mrc.controller  = controller

    registry.hw.add_mrc(mrc)

    if do_connect:
        return mrc.connect()

    return None

def run_add_mrc_config_dialog(find_data_file, registry, parent_widget=None):
    urls_in_use = [mrc.url for mrc in registry.cfg.get_mrcs()]
    serial_ports = util.list_serial_ports()
    dialog = AddMRCDialog(find_data_file=find_data_file, serial_ports=serial_ports,
            urls_in_use=urls_in_use, parent=parent_widget)
    dialog.setModal(True)

    def accepted():
        url, connect = dialog.result()
        mrc = cm.MRC(url)
        registry.cfg.add_mrc(mrc)

        if connect:
            mrc = registry.hw.get_mrc(url)
            if not mrc:
                add_mrc_connection(registry, url, True)
            elif mrc.is_disconnected():
                mrc.connect()

    dialog.accepted.connect(accepted)
    dialog.show()

def run_add_mrc_connection_dialog(find_data_file, registry, parent_widget=None):
    urls_in_use = [mrc.url for mrc in registry.hw.get_mrcs()]
    serial_ports = util.list_serial_ports()
    dialog = AddMRCDialog(find_data_file, serial_ports=serial_ports, urls_in_use=urls_in_use,
            do_connect_default=True, parent=parent_widget)
    dialog.setModal(True)

    def accepted():
        try:
            url, connect = dialog.result()
            add_mrc_connection(registry, url, connect)
        except Exception as e:
            log.exception("run_add_mrc_connection_dialog")
            QtGui.QMessageBox.critical(parent_widget, "Error", str(e))

    dialog.accepted.connect(accepted)
    dialog.show()

def run_add_device_config_dialog(device_registry, registry, mrc, bus=None, parent_widget=None):
    try:
        aa = [(b, d) for b in bm.BUS_RANGE for d in bm.DEV_RANGE
                if not mrc.cfg or not mrc.cfg.get_device(b, d)]

        dialog = AddDeviceDialog(bus=bus, available_addresses=aa,
                known_idcs=device_registry.get_device_names(), parent=parent_widget)
        dialog.setModal(True)

        def accepted():
            bus, address, idc, name = dialog.result()
            device_config = cm.make_device_config(bus, address, idc, name, device_registry.get_profile(idc))
            if not mrc.cfg:
                registry.cfg.add_mrc(cm.MRC(mrc.url))
            mrc.cfg.add_device(device_config)

        dialog.accepted.connect(accepted)
        dialog.show()
    except RuntimeError as e:
        log.exception(e)
        QtGui.QMessageBox.critical(parent_widget, "Error", str(e))

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
    if context.setup.modified:
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
        setup = config_xml.read_setup(filename)
        
        if not len(setup):
            raise RuntimeError("No MRC configurations found in %s" % filename)

        context.setup = setup
        context.make_qsettings().setValue('Files/last_setup_file', filename)
        return True

    except Exception as e:
        log.exception(e)
        QtGui.QMessageBox.critical(parent_widget, "Error", "Opening setup file %s failed:\n%s" % (filename, e))
        return False

def run_close_setup(context, parent_widget):
    if context.setup.modified:
        do_save = QtGui.QMessageBox.question(parent_widget,
                "Setup modified",
                "The current setup is modified. Do you want to save it?",
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
                QtGui.QMessageBox.Yes)
        if do_save == QtGui.QMessageBox.Yes:
            run_save_setup_as_dialog(context, parent_widget)

    context.reset_setup()

class GUIApplication(QtCore.QObject):
    """GUI logic"""
    def __init__(self, context, mainwindow):
        super(GUIApplication, self).__init__()
        self.log            = util.make_logging_source_adapter(__name__, self)
        self._mainwindow    = weakref.ref(mainwindow)
        self.context        = context
        self._linked_mode   = False
        self._hw_tables     = dict() # (app_model.Device) -> QMdiSubWindow
        self._cfg_tables    = dict() # (app_model.Device) -> QMdiSubWindow
        self._linked_tables = dict() # (app_model.Device) -> QMdiSubWindow

        # Treeview
        self.treeview = self.mainwindow.treeview
        self.treeview.linked_mode_changed.connect(self.set_linked_mode)

        self.treeview.cfg_context_menu_requested.connect(self._cfg_context_menu)
        self.treeview.hw_context_menu_requested.connect(self._hw_context_menu)

        self.treeview.node_activated.connect(self._tree_node_activated)

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

        self.app_registry.hw.mrc_added.connect(self._hw_mrc_added)

    def get_mainwindow(self):
        return self._mainwindow()

    def set_linked_mode(self, linked_mode):
        if self._linked_mode == linked_mode:
            return
        self._linked_mode = linked_mode
        # TODO: link mode transition here

    def get_linked_mode(self):
        return self._linked_mode

    mainwindow      = property(get_mainwindow)
    app_registry    = property(lambda self: self.context.app_registry)
    device_registry = property(lambda self: self.context.device_registry)
    linked_mode     = property(get_linked_mode, set_linked_mode)

    # MRC connection state changes
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

    def _add_device_table_window(self, device, show_hw, show_cfg):
        widget = device_tableview.DeviceTableWidget(device=device,
                find_data_file=self.context.find_data_file,
                show_hw=show_hw, show_cfg=show_cfg)

        print "_add_device_table_window", show_hw, show_cfg

        idc = device.hw.idc if show_hw else device.cfg.idc

        prefix = 'hw' if show_hw and not show_cfg else 'cfg' if show_cfg and not show_hw else 'linked'
        name   = "%s_(%s, %d, %d)" % (prefix, device.mrc.url, device.bus, device.address)
        title  = "%s @ (%s, %d, %d)" % (self.device_registry.get_device_name(idc),
                device.mrc.get_display_url(), device.bus, device.address)

        if show_cfg and len(device.cfg.name):
            title = "%s - %s" % (device.cfg.name, title)

        subwin = self._add_subwindow(widget, title, name)

        if show_hw and show_cfg:
            self._linked_tables[device] = subwin
        elif show_hw:
            self._hw_tables[device] = subwin
        else:
            self._cfg_tables[device] = subwin

        return subwin

    def _add_subwindow(self, widget, title=str(), name=str()):
        subwin = self.mainwindow.mdiArea.addSubWindow(widget)
        subwin.setWindowTitle(title)
        subwin.setObjectName(name)

        subwin.installEventFilter(self)
        restore_subwindow_state(subwin, self.context.make_qsettings())
        subwin.show()

        # TODO
        #action = QtGui.QAction(title, self, triggered=self._menu_window_action_triggered)
        #action.setData(name)
        #self.menu_Window.addAction(action)
        return subwin

    def _cfg_context_menu(self, node, idx, pos, view):
        menu = QtGui.QMenu()

        if isinstance(node, ctm.SetupNode):
            setup = node.ref.cfg

            menu.addAction("Open Setup").triggered.connect(partial(run_open_setup_dialog,
                context=self.context, parent_widget=self.treeview))

            #menu.addAction("Load Setup")

            if len(setup):
                if len(setup.filename):
                    menu.addAction("Save Setup").triggered.connect(partial(run_save_setup,
                        context=self.context, parent_widget=self.treeview))

                menu.addAction("Save Setup As").triggered.connect(partial(run_save_setup_as_dialog,
                    context=self.context, parent_widget=self.treeview))

                menu.addAction("Close Setup").triggered.connect(partial(run_close_setup,
                    context=self.context, parent_widget=self.treeview))

            menu.addAction("Add MRC").triggered.connect(partial(run_add_mrc_config_dialog,
                find_data_file=self.context.find_data_file, registry=self.app_registry,
                parent_widget=self.treeview))

        if isinstance(node, ctm.MRCNode):
            menu.addAction("Add Device").triggered.connect(partial(run_add_device_config_dialog,
                device_registry=self.context.device_registry, registry=self.app_registry,
                mrc=node.ref, parent_widget=self.treeview))

            def remove_mrc():
                self.app_registry.cfg.remove_mrc(node.ref.cfg)

            #menu.addAction("Edit MRC").triggered.connect(partial(run_edit_mrc_config_dialog,
            #    context=self.context, registry=self.registry, mrc=node.ref, parent_widget=self.treeview))
            menu.addAction("Remove MRC").triggered.connect(remove_mrc)

        if isinstance(node, ctm.BusNode):
            menu.addAction("Add Device").triggered.connect(partial(run_add_device_config_dialog,
                device_registry=self.context.device_registry, registry=self.app_registry,
                mrc=node.parent.ref, bus=node.bus_number, 
                parent_widget=self.treeview))

        if isinstance(node, ctm.DeviceNode):
            menu.addAction("Open").triggered.connect(partial(self._add_device_table_window, device=node.ref))
            menu.addAction("Load From File")
            menu.addAction("Save To File")
            menu.addAction("Remove Device from Config")

        if not menu.isEmpty():
            menu.exec_(view.mapToGlobal(pos))


    def _hw_context_menu(self, node, idx, pos, view):
        menu = QtGui.QMenu()

        if isinstance(node, htm.RegistryNode):
            menu.addAction("Add MRC Connection").triggered.connect(partial(run_add_mrc_connection_dialog,
                find_data_file=self.context.find_data_file, registry=self.app_registry, parent_widget=self.treeview))

        if isinstance(node, htm.MRCNode):
            mrc = node.ref

            if not mrc.hw or mrc.hw.is_disconnected():
                def do_connect():
                    if not mrc.hw:
                        add_mrc_connection(self.app_registry, mrc.url, True)
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
            hw = node.ref.hw
            menu.addAction("Open").triggered.connect(partial(self._add_device_table_window, device=node.ref))
            if hw is not None:
                def toggle_polling():
                    hw.polling = not hw.polling

                menu.addAction("Disable polling" if hw.polling else "Enable polling").triggered.connect(toggle_polling)

        if not menu.isEmpty():
            menu.exec_(view.mapToGlobal(pos))

    def _tree_node_activated(self, node):
        is_device_cfg = isinstance(node, ctm.DeviceNode)
        is_device_hw  = isinstance(node, htm.DeviceNode)

        if is_device_cfg or is_device_hw:
            self._show_or_create_device_table_window(node.ref, is_device_cfg, is_device_hw)

    def _show_or_create_device_table_window(self, device, show_cfg, show_hw):
        if not show_cfg and not show_hw and not self.linked_mode:
            return

        if self.linked_mode:
            table_dict = self._linked_tables
        elif show_cfg:
            table_dict = self._cfg_tables
        elif show_hw:
            table_dict = self._hw_tables

        subwin = table_dict.get(device, None)

        if subwin is None:
            subwin = self._add_device_table_window(
                    device   = device,
                    show_cfg = self.linked_mode or show_cfg,
                    show_hw  = self.linked_mode or show_hw)

            table_dict[device] = subwin
            subwin.device = device
            subwin.table_dict = table_dict

        if subwin.isMinimized():
            subwin.showNormal()

        self.mainwindow.mdiArea.setActiveSubWindow(subwin)

    def eventFilter(self, watched_object, event):
        if (event.type() == QtCore.QEvent.Close
                and isinstance(watched_object, QtGui.QMdiSubWindow)):
            store_subwindow_state(watched_object, self.context.make_qsettings())
            if hasattr(watched_object, 'device') and hasattr(watched_object, 'table_dict'):
                del watched_object.table_dict[watched_object.device]

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
        uic.loadUi(context.find_data_file('mesycontrol/ui/mainwin.ui'), self)

        # Treeview
        self.treeview = MCTreeView(app_registry=context.app_registry,
                device_registry=context.device_registry, find_data_file=context.find_data_file)

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
