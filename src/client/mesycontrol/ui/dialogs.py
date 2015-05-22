#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import collections
from .. qt import Qt
from .. qt import QtGui
from .. import basic_model as bm

class EatReturnCombo(QtGui.QComboBox):
    def keyPressEvent(self, e):
        super(EatReturnCombo, self).keyPressEvent(e)
        if e.key() in (Qt.Key_Enter, Qt.Key_Return):
            e.accept() # accept the event so it won't be propagated

class AddMRCDialog(QtGui.QDialog):
    Result = collections.namedtuple("Result", "url name connect")

    def __init__(self, context, serial_ports, urls_in_use=list(), title="Add MRC", parent=None):
        super(AddMRCDialog, self).__init__(parent)
        self.urls_in_use = urls_in_use
        uic.loadUi(context.find_data_file('mesycontrol/ui/connect_dialog.ui'), self)

        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(False)
        self.combo_serial_port.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+'), None))
        self.le_tcp_host.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+'), None))
        self.le_mesycontrol_host.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+'), None))
        self.le_tcp_host.setText('localhost')
        self.le_mesycontrol_host.setText('localhost')

        for port in serial_ports:
            self.combo_serial_port.addItem(port)

        for le in self.findChildren(QtGui.QLineEdit):
            le.textChanged.connect(self._validate_inputs)

        for combo in self.findChildren(QtGui.QComboBox):
            combo.currentIndexChanged.connect(self._validate_inputs)
            combo.editTextChanged.connect(self._validate_inputs)

        self.stacked_widget.currentChanged.connect(self._validate_inputs)
        self._validate_inputs()

    def _validate_inputs(self):
        page_widget = self.stacked_widget.currentWidget()
        is_ok = all(le.hasAcceptableInput() for le in page_widget.findChildren(QtGui.QLineEdit))
        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(is_ok)

    # XXX: leftoff. get args and let a util function build a URL from them
    def accept(self):
        self.connection_config      = config.MRCConnectionConfig()

        idx = self.stacked_widget.currentIndex()
        if idx == 0:
            self.connection_config.serial_device    = self.combo_serial_port.currentText()
            baud_text = self.combo_baud_rate.currentText()
            baud_rate = int(baud_text) if baud_text != 'auto' else 0
            self.connection_config.serial_baud_rate = baud_rate
        elif idx == 1:
            self.connection_config.tcp_host = self.le_tcp_host.text()
            self.connection_config.tcp_port = self.spin_tcp_port.value()
        elif idx == 2:
            self.connection_config.mesycontrol_host = self.le_mesycontrol_host.text()
            self.connection_config.mesycontrol_port = self.spin_mesycontrol_port.value()

        super(ConnectDialog, self).accept()

class AddDeviceDialog(QtGui.QDialog):
    Result = collections.namedtuple("Result", "bus address idc name")

    def __init__(self, bus=None,
            available_addresses=[(b, d) for b in bm.BUS_RANGE for d in bm.DEV_RANGE],
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

            self.accept()

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

    #QtGui.QApplication.setDesktopSettingsAware(False)
    a = QtGui.QApplication([])
    #a.setStyle(QtGui.QStyleFactory.create("Cleanlooks"))
    #a.setStyle(QtGui.QStyleFactory.create("Plastique"))
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
