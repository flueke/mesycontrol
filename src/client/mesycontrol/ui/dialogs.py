#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2021 mesytec GmbH & Co. KG <info@mesytec.com>
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

import collections
from mesycontrol.qt import Qt
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui
from mesycontrol.qt import QtWidgets
from mesycontrol import basic_model as bm
from mesycontrol import util

class EatReturnCombo(QtWidgets.QComboBox):
    def keyPressEvent(self, e):
        super(EatReturnCombo, self).keyPressEvent(e)
        if e.key() in (Qt.Key_Enter, Qt.Key_Return):
            e.accept() # accept the event so it won't be propagated

class AddMRCDialog(QtWidgets.QDialog):
    Result = collections.namedtuple("Result", "url connect autoconnect")
    SERIAL_USB, SERIAL_SERIAL, TCP, MC = range(4)

    def __init__(self, serial_ports_usb, serial_ports_serial,
            urls_in_use=list(), url=None,
            do_connect_default=True, autoconnect_default=True,
            title="Add MRC", parent=None):
        super(AddMRCDialog, self).__init__(parent)
        self.urls_in_use = urls_in_use
        self.ui = util.loadUi(":/ui/connect_dialog.ui")
        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.ui)

        self.setWindowTitle(title)
        self.ui.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)

        self.ui.accepted.connect(self.accept)
        self.ui.rejected.connect(self.reject)

        for combo in (self.ui.combo_serial_port_usb, self.ui.combo_serial_port_serial):
            combo.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+'), None))

        self.ui.le_tcp_host.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+'), None))
        self.ui.le_mesycontrol_host.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+'), None))
        self.ui.le_tcp_host.setText('localhost')
        self.ui.le_mesycontrol_host.setText('localhost')
        self.ui.cb_connect.setChecked(do_connect_default)
        self.ui.cb_autoconnect.setChecked(autoconnect_default)

        for port in serial_ports_usb:
            self.ui.combo_serial_port_usb.addItem(port)

        for port in serial_ports_serial:
            self.ui.combo_serial_port_serial.addItem(port)

        for le in self.ui.findChildren(QtWidgets.QLineEdit):
            le.textChanged.connect(self._validate_inputs)

        for combo in self.ui.findChildren(QtWidgets.QComboBox):
            combo.currentIndexChanged.connect(self._validate_inputs)
            combo.editTextChanged.connect(self._validate_inputs)

        for spin in self.ui.findChildren(QtWidgets.QSpinBox):
            spin.valueChanged.connect(self._validate_inputs)

        self.ui.stacked_widget.currentChanged.connect(self._validate_inputs)
        self._validate_inputs()

        self._result = None

        if url is not None:
            self._set_url(url)

    def _validate_inputs(self):
        page_widget = self.ui.stacked_widget.currentWidget()
        is_ok = all(le.hasAcceptableInput() for le in page_widget.findChildren(QtWidgets.QLineEdit))
        is_ok = is_ok and not self._is_url_in_use(self._get_current_url())
        self.ui.buttonBox.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(is_ok)

    def _is_url_in_use(self, url):
        return len(self.urls_in_use) and any(util.mrc_urls_match(url, u) for u in self.urls_in_use)

    def _get_current_url(self):
        idx = self.ui.stacked_widget.currentIndex()

        if idx == AddMRCDialog.SERIAL_USB:
            baud_text = self.ui.combo_baud_rate_usb.currentText()
            baud_rate = int(baud_text) if baud_text != 'auto' else 0
            return util.build_connection_url(
                    serial_port=str(self.ui.combo_serial_port_usb.currentText()),
                    baud_rate=baud_rate)

        if idx == AddMRCDialog.SERIAL_SERIAL:
            baud_text = self.ui.combo_baud_rate_serial.currentText()
            baud_rate = int(baud_text) if baud_text != 'auto' else 0
            return util.build_connection_url(
                    serial_port=str(self.ui.combo_serial_port_serial.currentText()),
                    baud_rate=baud_rate)

        if idx == AddMRCDialog.TCP:
            return util.build_connection_url(
                    host=str(self.ui.le_tcp_host.text()),
                    port=self.ui.spin_tcp_port.value())

        if idx == AddMRCDialog.MC:
            return util.build_connection_url(
                    mc_host=str(self.ui.le_mesycontrol_host.text()),
                    mc_port=self.ui.spin_mesycontrol_port.value())

    def _set_url(self, url):
        d = util.parse_connection_url(url)

        if 'serial_port' in d:
            combo_port  = self.ui.combo_serial_port_usb
            combo_baud  = self.ui.combo_baud_rate_usb
            idx         = combo_port.findText(d['serial_port'])

            if idx < 0:
                combo_port  = self.ui.combo_serial_port_serial
                combo_baud  = self.ui.combo_baud_rate_serial
                idx         = combo_port.findText(d['serial_port'])

            if idx < 0:
                self.ui.combo_serial_port_serial.addItem(d['serial_port'])
                idx         = self.ui.combo_serial_port_serial.count() - 1
                combo_port  = self.ui.combo_serial_port_serial
                combo_baud  = self.ui.combo_baud_rate_serial

            combo_port.setCurrentIndex(idx)

            baud_text = str(d['baud_rate'])

            if baud_text == '0':
                baud_text = 'auto'

            idx = combo_baud.findText(baud_text)

            if idx < 0:
                combo_baud.addItem(baud_text)
                idx = self.ui.combo_baud.count() - 1

            combo_baud.setCurrentIndex(idx)

            idx = (AddMRCDialog.SERIAL_USB
                    if combo_port is self.ui.combo_serial_port_usb
                    else AddMRCDialog.SERIAL_SERIAL)

            self.ui.stacked_widget.setCurrentIndex(idx)
            self.ui.combo_type.setCurrentIndex(idx)

        if 'host' in d:
            self.ui.le_tcp_host.setText(d['host'])
            self.ui.spin_tcp_port.setValue(d['port'])
            self.ui.stacked_widget.setCurrentIndex(AddMRCDialog.TCP)
            self.ui.combo_type.setCurrentIndex(AddMRCDialog.TCP)

        if 'mc_host' in d:
            self.ui.le_mesycontrol_host.setText(d['mc_host'])
            self.ui.spin_mesycontrol_port.setValue(d['mc_port'])
            self.ui.stacked_widget.setCurrentIndex(AddMRCDialog.MC)
            self.ui.combo_type.setCurrentIndex(AddMRCDialog.MC)

    def accept(self):
        url  = self._get_current_url()
        connect = self.ui.cb_connect.isChecked()
        autoconnect = self.ui.cb_autoconnect.isChecked()
        self._result = AddMRCDialog.Result(url, connect, autoconnect)
        super(AddMRCDialog, self).accept()

    def result(self):
        return self._result

class AddDeviceDialog(QtWidgets.QDialog):
    Result = collections.namedtuple("Result", "bus address idc name")

    def __init__(self, bus=None, available_addresses=bm.ALL_DEVICE_ADDRESSES,
            known_idcs=list(), allow_custom_idcs=True, title="Add Device",
            selected_bus=None, selected_address=None, selected_idc=None,
            assigned_name=None,
            parent=None):
        """
        Dialog constructor.

        If `bus' is given the dialog will use it as the selected bus and won't
        allow the user to change the bus.

        `available_addresses` should be a list of (bus, address) pairs. These
        address pairs will be available for the user to choose from.

        `known_idcs` should be a list of (idc, name) pairs.

        If `allow_custom_idcs` is True the user may enter a custom IDC,
        otherwise only IDCs from `known_idcs` are selectable.

        If `known_idcs' is empty and `allow_custom_idcs' is False this method
        will raise an exception.

        If `selected_bus` and `selected_address` is not None the corresponding
        item will be preselected in the GUI.

        If `selected_idc` is not None the device type will be set using the given IDC
        and will not be modifyable.
        """

        if len(known_idcs) == 0 and not allow_custom_idcs:
            raise RuntimeError("No devices to choose from")

        if len(available_addresses) == 0 or (
                bus is not None and util.ilen_destructive(filter(
                    lambda x: x[0] == bus, available_addresses)) == 0):
            raise RuntimeError("No addresses available")

        super(AddDeviceDialog, self).__init__(parent)

        self.log = util.make_logging_source_adapter(__name__, self)

        self.setWindowTitle(title)
        self._result = None
        self.allow_custom_idcs = allow_custom_idcs

        self.bus_combo = QtWidgets.QComboBox()
        self.bus_combo.addItems([str(i) for i in bm.BUS_RANGE])

        self.address_combos = [QtWidgets.QComboBox() for i in bm.BUS_RANGE]

        for b, a in sorted(available_addresses):
            self.address_combos[b].addItem("%X" % a, a)

        self.address_combo_stack = QtWidgets.QStackedWidget()

        for combo in self.address_combos:
            self.address_combo_stack.addWidget(combo)

        self.bus_combo.activated.connect(self.address_combo_stack.setCurrentIndex)

        self.idc_combo = EatReturnCombo()
        for idc, name in sorted(known_idcs, key=lambda x: x[1]):
            self.idc_combo.addItem("%s (%d)" % (name, idc), idc)

        if self.idc_combo.findData(idc) < 0:
            self.idc_combo.addItem(str(idc), idc)

        if selected_idc is not None:
            self.log.debug("selected_idc=%d, idx=%d",
                    selected_idc, self.idc_combo.findData(selected_idc))

            self.idc_combo.setCurrentIndex(
                    self.idc_combo.findData(selected_idc))
            self.idc_combo.setEnabled(False)

        if bus is not None:
            self.bus_combo.setCurrentIndex(bus)
            self.address_combo_stack.setCurrentIndex(bus)

        self.name_input = QtWidgets.QLineEdit()

        if assigned_name is not None:
            self.name_input.setText(assigned_name)

        self.button_box = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)

        if allow_custom_idcs:
            self.idc_combo.setEditable(True)
            self.idc_combo.setValidator(QtGui.QIntValidator(1, 99))

            ok_button = self.button_box.button(QtWidgets.QDialogButtonBox.Ok)
            ok_button.setEnabled(len(known_idcs))

            def combo_index_changed():
                ok_button.setEnabled(True)

            def combo_le_text_edited():
                ok_button.setEnabled(self.idc_combo.lineEdit().hasAcceptableInput())

            self.idc_combo.currentIndexChanged.connect(combo_index_changed)
            self.idc_combo.lineEdit().textEdited.connect(combo_le_text_edited)

        if selected_bus is not None:
            assert selected_bus in bm.BUS_RANGE
            self.bus_combo.setCurrentIndex(selected_bus)
            self.address_combo_stack.setCurrentIndex(selected_bus)

            if selected_address is not None:
                assert selected_address in bm.DEV_RANGE
                combo = self.address_combo_stack.currentWidget()
                combo.setCurrentIndex(combo.findText("%X" % selected_address))

        def accept():
            bus = self.bus_combo.currentIndex()
            address = int(self.address_combos[bus].itemData(
                self.address_combos[bus].currentIndex()))

            if self.allow_custom_idcs and self.idc_combo.lineEdit().hasAcceptableInput():
                idc = int(self.idc_combo.lineEdit().text())
            else:
                idx = self.idc_combo.currentIndex()
                idc = int(self.idc_combo.itemData(idx))

            name = self.name_input.text()

            self._result = AddDeviceDialog.Result(
                    bus, address, idc, name)

            super(AddDeviceDialog, self).accept()

        self.button_box.accepted.connect(accept)
        self.button_box.rejected.connect(self.reject)

        layout = QtWidgets.QFormLayout(self)
        layout.addRow("Bus", self.bus_combo)
        layout.addRow("Address", self.address_combo_stack)
        layout.addRow("IDC", self.idc_combo)
        layout.addRow("Name", self.name_input)
        layout.addRow(self.button_box)

    def result(self):
        return self._result

if __name__ == "__main__":
    from functools import partial
    import sys

    a = QtWidgets.QApplication(sys.argv)

    dialogs = list()
    d = AddDeviceDialog()
    dialogs.append(d)

    d = AddDeviceDialog(bus=1)
    dialogs.append(d)

    d = AddDeviceDialog(available_addresses=[(0,1), (1,1), (0,15), (1,13)])
    dialogs.append(d)

    d = AddDeviceDialog(bus=1, available_addresses=[(0,1), (1,1), (0,15), (1,13)])
    dialogs.append(d)

    d = AddDeviceDialog(known_idcs=[(42, 'MHV4'), (41, 'MSCF16'), (21, 'MCFD16')])
    dialogs.append(d)

    d = AddDeviceDialog(known_idcs=[(42, 'MHV4'), (41, 'MSCF16'), (21, 'MCFD16')], allow_custom_idcs=False)
    dialogs.append(d)

    def print_result(d):
        print(d.result())

    for d in dialogs:
        d.accepted.connect(partial(print_result, d))
        d.show()

    a.exec_()
