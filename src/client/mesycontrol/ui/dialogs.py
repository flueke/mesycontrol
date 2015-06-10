#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import collections
from .. qt import Qt
from .. qt import QtCore
from .. qt import QtGui
from .. qt import uic
from .. import basic_model as bm
from .. import util

class EatReturnCombo(QtGui.QComboBox):
    def keyPressEvent(self, e):
        super(EatReturnCombo, self).keyPressEvent(e)
        if e.key() in (Qt.Key_Enter, Qt.Key_Return):
            e.accept() # accept the event so it won't be propagated

class AddMRCDialog(QtGui.QDialog):
    Result = collections.namedtuple("Result", "url connect")
    SERIAL, TCP, MC = range(3)

    def __init__(self, context, serial_ports, urls_in_use=list(), url=None,
            do_connect_default=False, title="Add MRC", parent=None):
        super(AddMRCDialog, self).__init__(parent)
        self.urls_in_use = urls_in_use
        uic.loadUi(context.find_data_file('mesycontrol/ui/connect_dialog.ui'), self)

        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(False)
        self.combo_serial_port.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+'), None))
        self.le_tcp_host.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+'), None))
        self.le_mesycontrol_host.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+'), None))
        self.le_tcp_host.setText('localhost')
        self.le_mesycontrol_host.setText('localhost')
        self.cb_connect.setChecked(do_connect_default)

        for port in serial_ports:
            self.combo_serial_port.addItem(port)

        for le in self.findChildren(QtGui.QLineEdit):
            le.textChanged.connect(self._validate_inputs)

        for combo in self.findChildren(QtGui.QComboBox):
            combo.currentIndexChanged.connect(self._validate_inputs)
            combo.editTextChanged.connect(self._validate_inputs)

        for spin in self.findChildren(QtGui.QSpinBox):
            spin.valueChanged.connect(self._validate_inputs)

        self.stacked_widget.currentChanged.connect(self._validate_inputs)
        self._validate_inputs()

        self._result = None

        if url is not None:
            self._set_url(url)

    def _validate_inputs(self):
        page_widget = self.stacked_widget.currentWidget()
        is_ok = all(le.hasAcceptableInput() for le in page_widget.findChildren(QtGui.QLineEdit))
        is_ok = is_ok and not self._is_url_in_use(self._get_current_url())
        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(is_ok)

    def _is_url_in_use(self, url):
        return len(self.urls_in_use) and any(util.mrc_urls_match(url, u) for u in self.urls_in_use)

    def _get_current_url(self):
        idx = self.stacked_widget.currentIndex()
        if idx == AddMRCDialog.SERIAL:
            baud_text = self.combo_baud_rate.currentText()
            baud_rate = int(baud_text) if baud_text != 'auto' else 0
            return util.build_connection_url(
                    serial_port=str(self.combo_serial_port.currentText()),
                    baud_rate=baud_rate)

        if idx == AddMRCDialog.TCP:
            return util.build_connection_url(
                    host=str(self.le_tcp_host.text()),
                    port=self.spin_tcp_port.value())

        if idx == AddMRCDialog.MC:
            return util.build_connection_url(
                    mc_host=str(self.le_mesycontrol_host.text()),
                    mc_port=self.spin_mesycontrol_port.value())

    def _set_url(self, url):
        d = util.parse_connection_url(url)

        if 'serial_port' in d:
            idx = self.combo_serial_port.findText(d['serial_port'])
            if idx < 0:
                self.combo_serial_port.addItem(d['serial_port'])
                idx = self.combo_serial_port.count() - 1
            self.combo_serial_port.setCurrentIndex(idx)

            baud_text = str(d['baud_rate'])

            if baud_text == '0':
                baud_text = 'auto'

            idx = self.combo_baud_rate.findText(baud_text)

            if idx < 0:
                self.combo_baud_rate.addItem(baud_text)
                idx = self.combo_baud_rate.count() - 1

            self.combo_baud_rate.setCurrentIndex(idx)

            self.stacked_widget.setCurrentIndex(AddMRCDialog.SERIAL)

        if 'host' in d:
            self.le_tcp_host.setText(d['host'])
            self.spin_tcp_port.setValue(d['port'])
            self.stacked_widget.setCurrentIndex(AddMRCDialog.TCP)

        if 'mc_host' in d:
            self.le_mesycontrol_host.setText(d['mc_host'])
            self.spin_mesycontrol_port.setValue(d['mc_port'])
            self.stacked_widget.setCurrentIndex(AddMRCDialog.MC)

    def accept(self):
        url  = self._get_current_url()
        connect = self.cb_connect.isChecked()
        self._result = AddMRCDialog.Result(url, connect)
        super(AddMRCDialog, self).accept()

    def result(self):
        return self._result

class AddDeviceDialog(QtGui.QDialog):
    Result = collections.namedtuple("Result", "bus address idc name")

    def __init__(self, bus=None, available_addresses=bm.ALL_DEVICE_ADDRESSES,
            known_idcs=list(), allow_custom_idcs=True, title="Add Device", parent=None):
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
        """

        if len(known_idcs) == 0 and not allow_custom_idcs:
            raise RuntimeError("No devices to choose from")

        if len(available_addresses) == 0 or (
                bus is not None and len(filter(
                    lambda x: x[0] == bus, available_addresses)) == 0):
            raise RuntimeError("No addresses available")

        super(AddDeviceDialog, self).__init__(parent)

        self.setWindowTitle(title)
        self._result = None
        self.allow_custom_idcs = allow_custom_idcs

        self.bus_combo = QtGui.QComboBox()
        self.bus_combo.addItems([str(i) for i in bm.BUS_RANGE])

        self.address_combos = [QtGui.QComboBox() for i in bm.BUS_RANGE]

        for b, a in sorted(available_addresses):
            self.address_combos[b].addItem(str(a), a)

        self.address_combo_stack = QtGui.QStackedWidget()
        
        for combo in self.address_combos:
            self.address_combo_stack.addWidget(combo)

        self.bus_combo.activated.connect(self.address_combo_stack.setCurrentIndex)

        self.idc_combo = EatReturnCombo()
        for idc, name in sorted(known_idcs, key=lambda x: x[1]):
            self.idc_combo.addItem("%s (%d)" % (name, idc), idc)

        if bus is not None:
            self.bus_combo.setCurrentIndex(bus)
            self.bus_combo.setEnabled(False)
            self.address_combo_stack.setCurrentIndex(bus)

        self.name_input = QtGui.QLineEdit()

        self.button_box = QtGui.QDialogButtonBox(
                QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)

        if allow_custom_idcs:
            self.idc_combo.setEditable(True)
            self.idc_combo.setValidator(QtGui.QIntValidator(1, 99))

            ok_button = self.button_box.button(QtGui.QDialogButtonBox.Ok)
            ok_button.setEnabled(len(known_idcs))

            def combo_index_changed():
                ok_button.setEnabled(True)

            def combo_le_text_edited():
                ok_button.setEnabled(self.idc_combo.lineEdit().hasAcceptableInput())

            self.idc_combo.currentIndexChanged.connect(combo_index_changed)
            self.idc_combo.lineEdit().textEdited.connect(combo_le_text_edited)

        def accept():
            bus = self.bus_combo.currentIndex()
            address, ok = self.address_combos[bus].itemData(
                    self.address_combos[bus].currentIndex()).toInt()

            if self.allow_custom_idcs and self.idc_combo.lineEdit().hasAcceptableInput():
                idc = int(self.idc_combo.lineEdit().text())
            else:
                idx = self.idc_combo.currentIndex()
                idc = self.idc_combo.itemData(idx)
                idc, _ = idc.toInt()

            name = str(self.name_input.text())

            self._result = AddDeviceDialog.Result(
                    bus, address, idc, name)

            super(AddDeviceDialog, self).accept()

        self.button_box.accepted.connect(accept)
        self.button_box.rejected.connect(self.reject)

        layout = QtGui.QFormLayout(self)
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

    a = QtGui.QApplication(sys.argv)

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
        print d.result()

    for d in dialogs:
        d.accepted.connect(partial(print_result, d))
        d.show()

    a.exec_()
