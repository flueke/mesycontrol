#!/usr/bin/env python
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
#
__author__ = 'Florian Lüke'
__email__  = 'florianlueke@gmx.net'

__author__ = 'Florian Lüke'
__email__  = 'florianlueke@gmx.net'

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
        self.log = util.make_logging_source_adapter(__name__, self)
        self.setWidget(widget)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.window_name_prefix = window_name_prefix
        self._linked_mode = False
        self.update_title_and_name()
        self.setWindowIcon(util.make_icon(":/window-icon.png"))

        widget.display_mode_changed.connect(self.update_title_and_name)
        widget.write_mode_changed.connect(self.update_title_and_name)

        self.device.config_set.connect(self._on_device_config_set)
        self.device.hardware_set.connect(self._on_device_hardware_set)
        self._on_device_config_set(self.device, None, self.device.cfg)
        self._on_device_hardware_set(self.device, None, self.device.hw)

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

    def set_linked_mode(self, linked_mode):
        self._linked_mode = linked_mode
        self.update_title_and_name()

    def get_linked_mode(self):
        return self._linked_mode

    device          = property(lambda s: s.get_device())
    display_mode    = property(get_display_mode, set_display_mode)
    write_mode      = property(get_write_mode, set_write_mode)
    linked_mode     = property(get_linked_mode, set_linked_mode)

    def update_title_and_name(self):
        """Updates the window title and the object name taking into account the
        display_mode and the device state."""
        device       = self.device
        idc          = None

        if self.display_mode == util.HARDWARE and device.has_hw:
            idc = device.hw_idc
        elif self.display_mode == util.CONFIG and device.has_cfg:
            idc = device.cfg_idc
        elif self.display_mode == util.COMBINED:
            if device.has_hw and device.has_cfg and not device.idc_conflict:
                idc = device.hw_idc
            elif device.has_cfg and not device.has_hw:
                idc = device.cfg_idc

        profile = device.hw_profile

        if idc is None:
            # The device is about to disappear and this window should close. Do
            # not attempt to update the title as no idc is known and device.mrc
            # will not be set.
            self.log.warning("update_title_and_name: idc is None -> early return")
            return

        profile = device.hw_profile if idc == device.hw_idc else device.cfg_profile

        prefixes = {
                util.COMBINED:  'combined',
                util.HARDWARE:  'hw',
                util.CONFIG:    'cfg',
                }

        device_type_name = profile.name

        name = "%s_%s_%s_(%s, %d, %d)" % (
                self.window_name_prefix, prefixes[self.display_mode],
                device_type_name, device.mrc.url, device.bus, device.address)

        title = "%s @ (%s, %d, %d)" % (
                device_type_name, device.mrc.get_display_url(),
                device.bus, device.address)

        if (device.has_cfg and len(device.cfg.name)
                and ((self.display_mode & util.CONFIG) or self.linked_mode)):
            title = "%s - %s" % (device.cfg.name, title)

        if self.device.idc_conflict:
            title = "%s - IDC conflict" % title

        if self.device.address_conflict:
            title = "%s - address conflict" % title

        title = "%s | display_mode=%s, write_mode=%s" % (
                title,
                util.RW_MODE_NAMES[self.display_mode],
                util.RW_MODE_NAMES[self.write_mode])

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

    def _on_device_hardware_set(self, app_device, old_hw, new_hw):
        signals = ['address_conflict_changed']

        if old_hw is not None:
            for signal in signals:
                getattr(old_hw, signal).disconnect(self.update_title_and_name)

        if new_hw is not None:
            for signal in signals:
                getattr(new_hw, signal).connect(self.update_title_and_name)


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

    def has_toolbar(self):
        try:
            return self.widget().has_toolbar()
        except AttributeError:
            return False

    def get_toolbar(self):
        return self.widget().get_toolbar()

class DeviceTableSubWindow(DeviceSubWindow):
    def __init__(self, widget, parent=None):
        super(DeviceTableSubWindow, self).__init__(
                widget=widget, window_name_prefix='table',
                parent=parent)

        self.resize(QtCore.QSize(600, 400))

    def has_combined_display(self):
        return True

    def has_toolbar(self):
        return True

    def get_toolbar(self):
        return self.widget().get_toolbar()

# ===== MRC =====
def run_add_mrc_config_dialog(registry, parent_widget=None):
    urls_in_use = [mrc.url for mrc in registry.cfg.get_mrcs()]
    serial_ports_usb = util.list_serial_ports(util.SERIAL_USB)
    serial_ports_serial = util.list_serial_ports(util.SERIAL_SERIAL)
    dialog = AddMRCDialog(
            serial_ports_usb=serial_ports_usb,
            serial_ports_serial=serial_ports_serial,
            urls_in_use=urls_in_use, parent=parent_widget)
    dialog.setModal(True)

    def accepted():
        url, connect, autoconnect = dialog.result()
        mrc = cm.MRC(url)
        mrc.autoconnect = autoconnect
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
    serial_ports_usb = util.list_serial_ports(util.SERIAL_USB)
    serial_ports_serial = util.list_serial_ports(util.SERIAL_SERIAL)
    dialog = AddMRCDialog(
            serial_ports_usb=serial_ports_usb,
            serial_ports_serial=serial_ports_serial,
            urls_in_use=urls_in_use,
            do_connect_default=True, parent=parent_widget)
    dialog.setModal(True)

    def accepted():
        try:
            url, connect, autoconnect = dialog.result()
            add_mrc_connection(registry.hw, url, connect)
        except Exception as e:
            log.exception("run_add_mrc_connection_dialog")
            QtGui.QMessageBox.critical(parent_widget, "Error", str(e))

    dialog.accepted.connect(accepted)
    dialog.show()

def run_edit_mrc_config(mrc, registry, parent_widget=None):
    urls_in_use = [mrc_.url for mrc_ in registry.cfg.get_mrcs()]
    urls_in_use.remove(mrc.url)
    serial_ports_usb = util.list_serial_ports(util.SERIAL_USB)
    serial_ports_serial = util.list_serial_ports(util.SERIAL_SERIAL)

    dialog = AddMRCDialog(
            serial_ports_usb=serial_ports_usb,
            serial_ports_serial=serial_ports_serial,
            urls_in_use=urls_in_use,
            url=mrc.url,
            do_connect_default=mrc.cfg.autoconnect,
            autoconnect_default=mrc.cfg.autoconnect,
            parent=parent_widget,
            title="Edit MRC config")
    dialog.setModal(True)

    def accepted(mrc=mrc):
        try:
            url, connect, autoconnect = dialog.result()

            if url == mrc.cfg.url and mrc.cfg.autoconnect == autoconnect:
                return

            device_configs = [d for d in mrc.cfg]

            for d in device_configs:
                mrc.cfg.remove_device(d)

            name = mrc.cfg.name
            registry.cfg.remove_mrc(mrc.cfg)

            new_mrc = cm.MRC(url)
            new_mrc.name = name
            new_mrc.autoconnect = autoconnect

            for d in device_configs:
                new_mrc.add_device(d)

            registry.cfg.add_mrc(new_mrc)

            if connect:
                mrc = registry.hw.get_mrc(url)
                if not mrc:
                    add_mrc_connection(registry.hw, url, connect)
                elif mrc.is_disconnected():
                    mrc.connect()

        except Exception as e:
            log.exception("run_edit_mrc_config")
            QtGui.QMessageBox.critical(parent_widget, "Error", str(e))

    dialog.accepted.connect(accepted)
    dialog.show()

# ===== Device =====
def run_add_device_config_dialog(device_registry, registry, mrc, bus=None, address=None, parent_widget=None):
    try:
        if address is None:
            aa = [(b, d) for b in bm.BUS_RANGE for d in bm.DEV_RANGE
                    if not mrc.cfg or not mrc.cfg.get_device(b, d)]
        else:
            assert bus is not None
            aa = [(bus, address)]

        dialog = AddDeviceDialog(bus=bus, available_addresses=aa,
                known_idcs=device_registry.get_device_names(), parent=parent_widget)
        dialog.setModal(True)

        def accepted():
            bus, address, idc, name = dialog.result()
            device_config = cm.make_device_config(bus, address, idc, name,
                    device_registry.get_device_profile(idc))
            if not mrc.has_cfg:
                registry.cfg.add_mrc(cm.MRC(mrc.url))
            mrc.cfg.add_device(device_config)

        dialog.accepted.connect(accepted)
        dialog.show()
    except RuntimeError as e:
        log.exception("add device config")
        QtGui.QMessageBox.critical(parent_widget, "Error", str(e))

def run_edit_device_config(device_registry, registry, device, parent_widget=None):
    assert device.cfg is not None
    mrc = device.mrc

    aa = [(b, d) for b in bm.BUS_RANGE for d in bm.DEV_RANGE
            if not mrc.cfg.get_device(b, d) or (b == device.bus and d == device.address)]

    dialog = AddDeviceDialog(
            selected_bus        = device.bus,
            selected_address    = device.address,
            selected_idc        = device.cfg.idc,
            assigned_name       = device.cfg.name,
            available_addresses = aa,
            known_idcs          = device_registry.get_device_names(),
            title               = "Edit device config",
            parent = parent_widget)
    dialog.setModal(True)

    def accepted():
        bus, address, idc, name = dialog.result()
        device_config = cm.make_device_config(bus, address, idc, name,
                device_registry.get_device_profile(idc))

        for k, v in device.cfg.extensions.iteritems():
            device_config.set_extension(k, v)

        for k, v in device.cfg.get_cached_memory_ref().iteritems():
            device_config.set_parameter(k, v)

        mrc.cfg.remove_device(device.cfg)
        mrc.cfg.add_device(device_config)

    dialog.accepted.connect(accepted)
    dialog.show()

def run_load_device_config(device, context, parent_widget):
    directory_hint = context.get_config_directory_hint()

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

        try:
            mrc.remove_device(device.cfg)
        except ValueError:
            pass

        mrc.add_device(config)
        context.set_config_directory_hint(filename)
        return True
    except Exception as e:
        log.exception("load device config")
        QtGui.QMessageBox.critical(parent_widget, "Error",
                "Loading device config from %s failed:\n%s" % (filename, e))
        return False

def run_save_device_config(device, context, parent_widget):
    directory_hint = context.get_config_directory_hint()

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
        context.set_config_directory_hint(filename)
        return True
    except Exception as e:
        log.exception("save device config")
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
        log.exception("save setup")
        QtGui.QMessageBox.critical(parent_widget, "Error", "Saving setup %s failed:\n%s" % (setup.filename, e))
        return False

def run_save_setup_as_dialog(context, parent_widget):
    setup = context.app_registry.cfg

    if len(setup.filename):
        directory_hint = setup.filename
    else:
        directory_hint = context.get_setup_directory_hint()

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

        context.set_setup_directory_hint(filename)
        return True
    except Exception as e:
        log.exception("save setup as")
        QtGui.QMessageBox.critical(parent_widget, "Error", "Saving setup %s failed:\n%s" % (setup.filename, e))
        return False
    
def run_open_setup_dialog(context, parent_widget):
    if context.setup.modified and len(context.setup):
        answer = QtGui.QMessageBox.question(parent_widget,
                "Setup modified",
                "The current setup is modified. Do you want to save it?",
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel,
                QtGui.QMessageBox.Yes)

        if answer == QtGui.QMessageBox.Cancel:
            return

        if answer == QtGui.QMessageBox.Yes:
            if not run_save_setup_as_dialog(context, parent_widget):
                return False

    directory_hint = context.get_setup_directory_hint()

    filename = str(QtGui.QFileDialog.getOpenFileName(
        parent_widget, "Open setup file",
        directory=directory_hint, filter="XML files (*.xml);; *"))

    if not len(filename):
        return False

    try:
        context.open_setup(filename)
    except Exception as e:
        log.exception("open setup")
        QtGui.QMessageBox.critical(parent_widget, "Error", "Opening setup file %s failed:\n%s" % (filename, e))
        return False

def run_close_setup(context, parent_widget):
    if context.setup.modified and len(context.setup):
        answer = QtGui.QMessageBox.question(parent_widget,
                "Setup modified",
                "The current setup is modified. Do you want to save it?",
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel,
                QtGui.QMessageBox.Yes)

        if answer == QtGui.QMessageBox.Cancel:
            return False

        if answer == QtGui.QMessageBox.Yes:
            run_save_setup_as_dialog(context, parent_widget)

    context.reset_setup()
    return True

# ===== node classifiers ===== #
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

def is_config(node):
    return isinstance(node, (ctm.SetupNode, ctm.MRCNode, ctm.BusNode, ctm.DeviceNode))

def is_hardware(node):
    return isinstance(node, (htm.RegistryNode, htm.MRCNode, htm.BusNode, htm.DeviceNode))

def is_device_cfg(node):
    return is_device(node) and is_config(node)

def is_device_hw(node):
    return is_device(node) and is_hardware(node)

def get_mrc(node):
    if is_mrc(node):
        return node.ref

    if is_bus(node) and node.parent is not None:
        return node.parent.ref

    if is_device(node):
        return node.ref.mrc

    return None

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
            size = settings.value(name + "_size").toSize()
            size = size.expandedTo(subwin.sizeHint())
            subwin.resize(size)

        if settings.contains(name + "_pos"):
            subwin.move(settings.value(name + "_pos").toPoint())

        return True
    finally:
        settings.endGroup()

# ===== Server log dview ===== #
class ServerLogView(QtGui.QPlainTextEdit):
    def __init__(self, server_process, max_lines=10000, line_wrap=QtGui.QPlainTextEdit.WidgetWidth, parent=None):
        super(ServerLogView, self).__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(max_lines)
        self.setLineWrapMode(line_wrap)
        self.server = server_process
        self.server.output.connect(self._on_server_output)

        for data in self.server.output_buffer:
            self.appendPlainText(data.strip())

    def _on_server_output(self, data):
        self.appendPlainText(data.trimmed())

class NotesTextEdit(QtGui.QPlainTextEdit):
    def __init__(self, parent=None):
        super(NotesTextEdit, self).__init__(parent)

    def setReadOnly(self, ro):
        pal = QtGui.QPalette()
        if ro:
            pal.setColor(QtGui.QPalette.Base, QtGui.QColor('lightgrey'))
        self.setPalette(pal)

        super(NotesTextEdit, self).setReadOnly(ro)

    def mouseDoubleClickEvent(self, event):
        if self.isReadOnly():
            self.setReadOnly(False)

        super(NotesTextEdit, self).mouseDoubleClickEvent(event)


class DeviceNotesWidget(QtGui.QWidget):
    DISPLAY_ROWS = 3
    ADD_PIXELS_PER_ROW = 5

    def __init__(self, device, parent=None):
        super(DeviceNotesWidget, self).__init__(parent)

        self.device = device

        device.read_mode_changed.connect(self._on_device_read_mode_changed)
        device.write_mode_changed.connect(self._on_device_write_mode_changed)
        device.extension_changed.connect(self._on_device_extension_changed)

        self.text_edit = NotesTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.modificationChanged.connect(
                self._on_text_edit_modification_changed)

        fm = self.text_edit.fontMetrics()
        rh = fm.lineSpacing() + DeviceNotesWidget.ADD_PIXELS_PER_ROW
        self.text_edit.setFixedHeight(DeviceNotesWidget.DISPLAY_ROWS * rh)

        layout = QtGui.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.text_edit)

        self.edit_button = QtGui.QPushButton(util.make_icon(":/edit.png"), str(),
                clicked=self._on_edit_button_clicked)
        self.edit_button.setToolTip("Edit Device Notes")
        self.edit_button.setStatusTip(self.edit_button.toolTip())

        button_layout = QtGui.QVBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addWidget(self.edit_button, 0, Qt.AlignHCenter)
        button_layout.addStretch(1)

        layout.addLayout(button_layout)

        self._populate()

    def _on_device_read_mode_changed(self, read_mode):
        self._populate()

    def _on_device_write_mode_changed(self, write_mode):
        self._populate()

    def _on_device_extension_changed(self, name, value):
        if name == 'user_notes':
            self._populate()

    def _populate(self):
        with util.block_signals(self.text_edit):
            try:
                notes = self.device.get_extension('user_notes')
                if self.get_plain_text() != notes:
                    self.text_edit.setPlainText(notes)
            except KeyError:
                self.text_edit.clear()
            self.text_edit.document().setModified(False)

    def is_modified(self):
        return self.text_edit.document().isModified()

    def get_plain_text(self):
        return self.text_edit.toPlainText()

    def commit(self):
        if self.is_modified():
            self.device.set_extension('user_notes', self.text_edit.toPlainText())
            self.text_edit.document().setModified(False)

    def _on_edit_button_clicked(self):
        self.text_edit.setReadOnly(not self.text_edit.isReadOnly())

        if self.text_edit.isReadOnly():
            self.commit()

    def _on_text_edit_modification_changed(self, changed):
        if changed:
            self.commit()
