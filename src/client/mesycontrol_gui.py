#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import argparse
import logging
import logging.config
import logging.handlers
import os
import signal
import sys
import weakref
from functools import partial
from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSlot
from PyQt4.Qt import Qt
from mesycontrol import application_registry
from mesycontrol import device_view
from mesycontrol import config
from mesycontrol import config_xml
from mesycontrol import log_view
from mesycontrol import setup_treeview
from mesycontrol import util
from mesycontrol.ui.connect_dialog import ConnectDialog

def store_subwindow_state(subwin, settings):
    name = str(subwin.objectName())
    settings.beginGroup("MdiSubWindows")
    try:
        settings.setValue(name + "_size", subwin.size())
        settings.setValue(name + "_pos",  subwin.pos())
    finally:
        settings.endGroup()

def restore_subwindow_state(subwin, settings):
    name = str(subwin.objectName())

    settings.beginGroup("MdiSubWindows")
    try:
        if settings.contains(name + "_size"):
            subwin.resize(settings.value(name + "_size").toSize())

        if settings.contains(name + "_pos"):
            subwin.move(settings.value(name + "_pos").toPoint())
    finally:
        settings.endGroup()

class MainWindow(QtGui.QMainWindow):
    def __init__(self, parent = None):
        super(MainWindow, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.font_point_size = QtGui.QApplication.instance().font().pointSize()

        QtCore.QCoreApplication.instance().aboutToQuit.connect(self.on_qapp_quit)
        uic.loadUi(application_registry.instance.find_data_file('mesycontrol/ui/mainwin.ui'), self)

        # Setup Tree Dock Widget
        self.setup_tree_view = setup_treeview.SetupTreeView(parent=self)
        self.setup_tree_view.sig_open_device.connect(self._slt_open_device_window)
        self.setup_tree_view.sig_remove_mrc.connect(self._slt_remove_mrc_from_setup)
        application_registry.instance.mrc_added.connect(self.setup_tree_view.model().add_mrc)
        application_registry.instance.mrc_removed.connect(self.setup_tree_view.model().remove_mrc)

        dw_setup_tree = QtGui.QDockWidget("Setup", self)
        dw_setup_tree.setObjectName("dw_setup_tree")
        dw_setup_tree.setWidget(self.setup_tree_view)
        dw_setup_tree.setFeatures(QtGui.QDockWidget.DockWidgetMovable | QtGui.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.LeftDockWidgetArea, dw_setup_tree)

        # Log View Dock Widget
        log_emitter = util.QtLogEmitter(parent=self)
        logging.getLogger().addHandler(log_emitter.get_handler())

        self.log_view = log_view.LogView(parent=self)
        log_emitter.log_record.connect(self.log_view.handle_log_record)
        application_registry.instance.register('exception_logger', self.log_view.handle_exception)

        dw_log_view = QtGui.QDockWidget("Application Log", self)
        dw_log_view.setObjectName("dw_log_view")
        dw_log_view.setWidget(self.log_view)
        dw_log_view.setFeatures(QtGui.QDockWidget.DockWidgetMovable | QtGui.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dw_log_view)

        # Mapping of: Device -> Subwindow
        self._device_windows = dict()

        application_registry.instance.device_added.connect(self._on_application_registry_device_added)
        application_registry.instance.active_setup_changed.connect(self._on_active_setup_changed)

        self.restore_settings()

    def store_settings(self):
        settings = application_registry.instance.make_qsettings()

        settings.beginGroup("MainWindow")

        try:
            settings.setValue("size",               self.size());
            settings.setValue("pos",                self.pos());
            settings.setValue("geometry",           self.saveGeometry());
            settings.setValue("state",              self.saveState());
            settings.setValue("font_point_size",    self.font_point_size);
        finally:
            settings.endGroup()

        window_list = self.mdiArea.subWindowList()

        for window in window_list:
            store_subwindow_state(window, settings)

    def restore_settings(self):
        settings = application_registry.instance.make_qsettings()

        settings.beginGroup("MainWindow")
        try:
            self.resize(settings.value("size", QtCore.QSize(1024, 768)).toSize())
            self.move(settings.value("pos", QtCore.QPoint(0, 0)).toPoint())
            self.restoreGeometry(settings.value("geometry").toByteArray())
            self.restoreState(settings.value("state").toByteArray())
            self.font_point_size, ignored = settings.value("font_point_size",
                    QtGui.QApplication.instance().font().pointSize()).toInt()
            self.change_font_size(0)
        finally:
            settings.endGroup()

    @pyqtSlot()
    def on_qapp_quit(self):
        logging.info("Exiting...")
        application_registry.instance.shutdown()

    @pyqtSlot()
    def on_actionConnect_triggered(self):
        dialog = ConnectDialog(self)
        result = dialog.exec_()

        if result != QtGui.QDialog.Accepted:
            return

        connection_config = dialog.connection_config
        connection        = application_registry.instance.find_connection_by_config(connection_config)

        if connection is not None:
            QtGui.QMessageBox.critical(self, "Connection error", "Connection exists")
            return

        application_registry.instance.make_mrc_connection(config=connection_config, connect=True)

    @pyqtSlot()
    def on_actionLoad_Setup_triggered(self):
        setup = application_registry.instance.get('active_setup')

        if setup is not None and setup.modified:
            do_save = QtGui.QMessageBox.question(
                    self,
                    "Setup modified",
                    "The current setup is modified. Do you want to save it?",
                    QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
                    QtGui.QMessageBox.Yes)
            if do_save == QtGui.QMessageBox.Yes:
                self.on_actionSave_Setup_As_triggered()

        directory_hint = os.path.dirname(str(application_registry.instance.make_qsettings().value(
                'Files/last_setup_file', QtCore.QString()).toString()))

        filename = QtGui.QFileDialog.getOpenFileName(self, "Open setup file",
                directory=directory_hint, filter="XML files (*.xml);; *")

        if not len(filename):
            return

        try:
            setup = config_xml.parse_file(filename)
        except config_xml.InvalidArgument as e:
            QtGui.QMessageBox.critical(self, "Error", "Opening setup %s failed: %s" % (filename, e))
            return

        if not len(setup.mrc_configs):
            QtGui.QMessageBox.critical(self, "Error", "No MRC configurations found in %s" % filename)
            return

        setup_loader = config.SetupLoader(setup)
        pd = QtGui.QProgressDialog(self)
        pd.setMaximum(0)
        pd.setValue(0)

        setup_loader.progress_changed.connect(pd.setValue)
        setup_loader.stopped.connect(pd.accept)
        QtCore.QTimer.singleShot(0, setup_loader.start)
        pd.exec_()

        if pd.wasCanceled():
            setup_loader.stop()

        if setup_loader.has_failed():
            QtGui.QMessageBox.critical(self, "Error", "Setup loading failed")

        application_registry.instance.make_qsettings().setValue(
                'Files/last_setup_file', filename)

    @pyqtSlot()
    def on_actionSave_Setup_As_triggered(self):
        directory_hint = str(application_registry.instance.make_qsettings().value(
                'Files/last_setup_file', QtCore.QString()).toString())

        setup = application_registry.instance.get('active_setup')

        if len(setup.filename):
            directory_hint = setup.filename
        else:
            directory_hint = os.path.dirname(directory_hint)

        filename = QtGui.QFileDialog.getSaveFileName(self, "Save setup as",
                directory=directory_hint, filter="XML files (*.xml);; *")

        if not len(filename):
            return

        self._save_setup_to_file(application_registry.instance.get('active_setup'),
                filename)

        application_registry.instance.make_qsettings().setValue(
                'Files/last_setup_file', filename)

    @pyqtSlot()
    def on_actionSave_Setup_triggered(self):
        setup = application_registry.instance.get('active_setup')

        if not len(setup.filename):
            self.on_actionSave_Setup_As_triggered()
            return

        self._save_setup_to_file(setup, setup.filename)

    def _save_setup_to_file(self, setup, filename):
        filename = str(filename)

        if not filename.endswith(".xml"):
            filename += ".xml"

        setup = application_registry.instance.get('active_setup')

        if setup is None:
            return

        # Make sure the device config instances within the setup are complete
        # (all required parameters present).
        setup_completer = config.SetupCompleter(setup)
        pd = QtGui.QProgressDialog(self)
        pd.setMaximum(len(setup_completer))
        pd.setValue(0)

        setup_completer.progress_changed.connect(pd.setValue)
        setup_completer.stopped.connect(pd.accept)
        QtCore.QTimer.singleShot(0, setup_completer.start)
        pd.exec_()

        if pd.wasCanceled():
            setup_completer.stop()

        if setup_completer.has_failed():
            QtGui.QMessageBox.critical(self, "Error", "Setup building failed")
        else:
            try:
                with open(filename, 'w') as f:
                    config_xml.write_setup_to_file(setup, f)
                    setup.filename = filename
                    setup.modified = False
                    application_registry.instance.make_qsettings().setValue(
                            'Files/last_setup_file', filename)
            except IOError as e:
                QtGui.QMessageBox.critical(self, "Error", "Writing to %s failed: %s" % (filename, e))
            else:
                QtGui.QMessageBox.information(self, "Info", "Configuration written to %s" % filename)
                application_registry.instance.make_qsettings().setValue(
                        'Files/last_setup_file', filename)

    @pyqtSlot()
    def on_actionClose_Setup_triggered(self):
        setup = application_registry.instance.get('active_setup')

        if setup is not None and setup.modified:
            do_save = QtGui.QMessageBox.question(
                    self,
                    "Setup modified",
                    "The current setup is modified. Do you want to save it?",
                    QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
                    QtGui.QMessageBox.Yes)
            if do_save == QtGui.QMessageBox.Yes:
                self.on_actionSave_Setup_As_triggered()

        application_registry.instance.register('active_setup', config.Setup())

        for mrc in application_registry.instance.get_mrcs():
            application_registry.instance.unregister_mrc(mrc)

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

    @pyqtSlot()
    def on_actionFont_Size_Inc_triggered(self):
        self.change_font_size(+1)

    @pyqtSlot()
    def on_actionFont_Size_Dec_triggered(self):
        self.change_font_size(-1)

    def change_font_size(self, delta):
        self.font_point_size += delta
        QtGui.QApplication.instance().setStyleSheet("QWidget { font-size: %dpt; }" % self.font_point_size)

    def _on_application_registry_device_added(self, device):
        self.log.debug("ApplicationRegistry added a new device: %s", device)
        device.name_changed.connect(partial(self._on_device_name_changed, device_ref=weakref.ref(device)))

    def _on_active_setup_changed(self, old_setup, new_setup):
        self.log.info("_on_active_setup_changed, %s, %s", old_setup, new_setup)
        if old_setup is not None:
            old_setup.modified_changed.disconnect(self._on_active_setup_modified)
        new_setup.modified_changed.connect(self._on_active_setup_modified)
        self._on_active_setup_modified()

    def _on_active_setup_modified(self, is_modified=False):
        setup = application_registry.instance.get('active_setup')
        setup_dock = self.findChild(QtGui.QDockWidget, 'dw_setup_tree')
        title = 'Unsaved Setup [*]'
        if len(setup.filename):
            title = 'Setup (%s)[*]' % setup.filename
        setup_dock.setWindowTitle(title)
        setup_dock.setWindowModified(setup.modified)

    def _on_device_name_changed(self, name, device_ref):
        device = device_ref() if device_ref is not None else None
        self.log.debug("Device name changed: device=%s, name=%s", device, name)

        try:
            subwin = self._device_windows[device]
            subwin.setWindowTitle(str(device))
        except KeyError:
            pass

    def _add_subwindow(self, widget, title, name):
        subwin = self.mdiArea.addSubWindow(widget)
        subwin.setWindowTitle(title)
        subwin.setObjectName(name)
        restore_subwindow_state(subwin, application_registry.instance.make_qsettings())
        subwin.show()

        action = QtGui.QAction(title, self, triggered=self._menu_window_action_triggered)
        action.setData(name)
        self.menu_Window.addAction(action)
        return subwin

    def _slt_open_device_window(self, device):
        subwin = None
        try:
            subwin = self._device_windows[device]
            self.log.debug("Found window for Device %s", device)
        except KeyError:
            self.log.debug("Creating window for Device %s", device)
            widget  = device_view.DeviceView(device, self)

            subwin = self._add_subwindow(widget, str(device), str(device))
            subwin.device = device
            subwin.installEventFilter(self)

            self._device_windows[device] = subwin

        subwin.show()
        subwin.widget().show()
        self.mdiArea.setActiveSubWindow(subwin)

    def _slt_remove_mrc_from_setup(self, mrc):
        mrc.disconnect()

        active_setup = application_registry.instance.get('active_setup')
        active_setup.remove_mrc_config(mrc.config)

        for device in mrc.get_devices():
            if device in self._device_windows:
                self.mdiArea.removeSubWindow(self._device_windows[device])

        application_registry.instance.unregister_mrc(mrc)

    @pyqtSlot()
    def _menu_window_action_triggered(self):
        name   = self.sender().data().toString()
        subwin = self.findChild(QtGui.QMdiSubWindow, name)

        subwin.show()
        subwin.widget().show()

        if subwin.isMinimized():
            subwin.showNormal()

        self.mdiArea.setActiveSubWindow(subwin)

    def eventFilter(self, watched_object, event):
        if event.type() == QtCore.QEvent.Close and hasattr(watched_object, 'device'):
            # A device window is about to be closed
            self.log.debug("Device Window for %s is closing", watched_object.device)
            del self._device_windows[watched_object.device]
            for action in self.menu_Window.actions():
                if action.data().toString() == watched_object.objectName():
                    self.menu_Window.removeAction(action)
                    break

        if event.type() == QtCore.QEvent.Close and isinstance(watched_object, QtGui.QMdiSubWindow):
            store_subwindow_state(watched_object, application_registry.instance.make_qsettings())

        return False # Do not filter out the event

    def closeEvent(self, event):
        self.store_settings()
        super(MainWindow, self).closeEvent(event)

def signal_handler(signum, frame):
    logging.info("Received signal %s. Quitting...",
            signal.signum_to_name.get(signum, "%d" % signum))
    QtGui.QApplication.quit()

def app_except_hook(exc_type, exc_value, exc_trace):
    if application_registry.instance is not None:
        exc_logger = application_registry.instance.get('exception_logger')
        if exc_logger is not None:
            exc_logger(exc_type, exc_value, exc_trace)

    sys.__excepthook__(exc_type, exc_value, exc_trace)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='mesycontrol GUI command line arguments')
    parser.add_argument('--logging-config', metavar='FILE')
    opts = parser.parse_args()

    # Logging setup
    if opts.logging_config is not None:
        logging.config.fileConfig(opts.logging_config)
    else:
        logging.basicConfig(level=logging.DEBUG,
                format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

        logging.getLogger("PyQt4.uic").setLevel(logging.INFO)
        #logging.getLogger("mesycontrol.tcp_client").setLevel(logging.DEBUG)

    logging.info("Starting up...")

    # Signal handling
    signal.signum_to_name = dict((getattr(signal, n), n)
            for n in dir(signal) if n.startswith('SIG') and '_' not in n)
    signal.signal(signal.SIGINT, signal_handler)

    sys.excepthook = app_except_hook

    # Qt setup
    QtCore.QLocale.setDefault(QtCore.QLocale.c())
    QtGui.QApplication.setDesktopSettingsAware(False)
    app = QtGui.QApplication(sys.argv)

    # Let the interpreter run every 500 ms to be able to react to signals
    # arriving from the OS.
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    # Confine garbage collection to the main thread to avoid crashes.
    garbage_collector = util.GarbageCollector()

    application_registry.instance = application_registry.ApplicationRegistry(
            sys.executable if getattr(sys, 'frozen', False) else __file__)

    mainwin = MainWindow()
    mainwin.show()
    ret = app.exec_()

    del mainwin
    del garbage_collector

    sys.exit(ret)
