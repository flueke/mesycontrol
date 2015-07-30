#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import Qt
from qt import QtCore
from qt import QtGui

import logging
import os

from model_util import add_mrc_connection
from ui.dialogs import AddDeviceDialog
from ui.dialogs import AddMRCDialog

import basic_model as bm
import config_model as cm
import config_tree_model as ctm
import config_xml
import hardware_tree_model as htm
import util

log = logging.getLogger(__name__)

class DeviceSubWindow(QtGui.QMdiSubWindow):
    def __init__(self, widget, window_name_prefix, parent=None, **kwargs):
        super(DeviceSubWindow, self).__init__(parent)
        self.setWidget(widget)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.window_name_prefix = window_name_prefix
        self.update_title_and_name()

        self.device.config_set.connect(self._on_device_config_set)
        self._on_device_config_set(self.device, None, self.device.cfg)

    def get_device(self):
        return self.widget().device

    def get_display_mode(self):
        return self.widget().display_mode

    def set_display_mode(self, mode):
        self.widget().display_mode = mode

    def get_write_mode(self):
        return self.widget().write_mode

    def set_write_mode(self, mode):
        self.widget().write_mode = mode

    def has_combined_display(self):
        raise NotImplementedError()

    def has_toolbar(self):
        return False

    def get_toolbar(self):
        raise NotImplementedError()

    device          = property(lambda s: s.get_device())
    display_mode    = property(get_display_mode, set_display_mode)
    write_mode      = property(get_write_mode, set_write_mode)

    def update_title_and_name(self):
        """Updates the window title and the object name taking into account the
        display_mode and the device state."""
        device       = self.device
        idc          = None

        if device.hw is not None:
            idc = device.hw.idc
        elif device.cfg is not None:
            idc = device.cfg.idc

        if idc is None:
            # The device is about to disappear and this window should close. Do
            # not attempt to update the title as no idc is known and device.mrc
            # will not be set.
            return

        prefixes = {
                util.COMBINED:  'combined',
                util.HARDWARE:  'hw',
                util.CONFIG:    'cfg',
                }

        device_name = device.get_device_name()

        name = "%s_%s_(%s, %d, %d)" % (
                self.window_name_prefix, prefixes[self.display_mode],
                device.mrc.url, device.bus, device.address)

        title = "%s @ (%s, %d, %d)" % (
                device_name, device.mrc.get_display_url(),
                device.bus, device.address)

        if ((self.display_mode & util.CONFIG)
                and device.cfg is not None
                and len(device.cfg.name)):
            title = "%s - %s" % (device.cfg.name, title)

        if self.device.idc_conflict:
            title = "%s - IDC conflict" % title

        if self.device.address_conflict:
            title = "%s - address conflict" % title

        if self.device.has_cfg and self.device.cfg.modified:
            title += " *"

        self.setWindowTitle(title)
        self.setObjectName(name)

    def _on_device_config_set(self, app_device, old_cfg, new_cfg):
        signals = ['modified_changed', 'name_changed']

        if old_cfg is not None:
            for signal in signals:
                getattr(old_cfg, signal).disconnect(self.update_title_and_name)

        if new_cfg is not None:
            for signal in signals:
                getattr(new_cfg, signal).connect(self.update_title_and_name)

class DeviceWidgetSubWindow(DeviceSubWindow):
    def __init__(self, widget, parent=None):
        super(DeviceWidgetSubWindow, self).__init__(
                widget=widget, window_name_prefix='widget',
                parent=parent)

    def get_device(self):
        return self.widget().device.app_device

    def get_specialized_device(self):
        return self.widget().device

    def has_combined_display(self):
        return False

class DeviceTableSubWindow(DeviceSubWindow):
    def __init__(self, widget, parent=None):
        super(DeviceTableSubWindow, self).__init__(
                widget=widget, window_name_prefix='table',
                parent=parent)

    def has_combined_display(self):
        return True

    def has_toolbar(self):
        return True

    def get_toolbar(self):
        return self.widget().get_toolbar()

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

def is_config_node(node):
    return isinstance(node, (ctm.SetupNode, ctm.MRCNode, ctm.BusNode, ctm.DeviceNode))

def is_hardware_node(node):
    return isinstance(node, (htm.RegistryNode, htm.MRCNode, htm.BusNode, htm.DeviceNode))

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

