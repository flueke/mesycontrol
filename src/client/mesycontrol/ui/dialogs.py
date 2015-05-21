#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import collections
from .. qt import Qt
from .. qt import QtCore
from .. qt import QtGui
from .. import basic_model as bm

class EatReturnCombo(QtGui.QComboBox):
    def keyPressEvent(self, e):
        super(EatReturnCombo, self).keyPressEvent(e)
        if e.key() in (Qt.Key_Enter, Qt.Key_Return):
            e.accept() # accept the event so it won't be propagated

class AddDeviceDialog(QtGui.QDialog):
    Result = collections.namedtuple("Result", "bus address idc name")

    def __init__(self, bus=None,
            available_addresses=[(b, d) for b in bm.BUS_RANGE for d in bm.DEV_RANGE],
            known_idcs=list(), allow_custom_idcs=True, parent=None):
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

        if len(available_addresses) == 0:
            raise RuntimeError("No addresses available")

        super(AddDeviceDialog, self).__init__(parent)
        self._result = None

        self.bus_combo = QtGui.QComboBox()
        self.bus_combo.addItems([str(i) for i in bm.BUS_RANGE])

        self.address_combos = [QtGui.QComboBox() for i in bm.BUS_RANGE]

        for b, a in sorted(available_addresses):
            self.address_combos[b].addItem(str(a), a)

        self.address_combo_stack = QtGui.QStackedWidget()
        
        for combo in self.address_combos:
            self.address_combo_stack.addWidget(combo)

        self.bus_combo.activated.connect(self.address_combo_stack.setCurrentIndex)

        #self.idc_combo = QtGui.QComboBox()
        self.idc_combo = EatReturnCombo()
        for idc, name in sorted(known_idcs, cmp=lambda a, b: cmp(a[1], b[1])):
            self.idc_combo.addItem("%s (%d)" % (name, idc), idc)

        if allow_custom_idcs:
            self.idc_combo.setEditable(True)
            self.idc_combo.setValidator(QtGui.QIntValidator(1, 99))

        if bus is not None:
            self.bus_combo.setCurrentIndex(bus)
            self.bus_combo.setEnabled(False)

        self.name_input = QtGui.QLineEdit()

        self.button_box = QtGui.QDialogButtonBox(
                QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)


        ok_button = self.button_box.button(QtGui.QDialogButtonBox.Ok)

        # XXX: leftoff FIXME: QComboBox sucks
        if allow_custom_idcs:
            ok_button.setEnabled(len(known_idcs))
            def idc_text_changed():
                is_known_idc = self.idc_combo.itemData(
                        self.idc_combo.currentIndex()).type() != QtCore.QVariant.Invalid
                print "text_changed", is_known_idc
                ok_button.setEnabled(is_known_idc or self.idc_combo.lineEdit().hasAcceptableInput())
            self.idc_combo.editTextChanged.connect(idc_text_changed)

        #def idc_text_changed():
        #    ok_button.setEnabled(self.idc_input.hasAcceptableInput())

        #self.idc_input.textChanged.connect(idc_text_changed)

        def accept():
            bus = self.bus_combo.currentIndex()
            address, ok = self.address_combos[bus].itemData(
                    self.address_combos[bus].currentIndex()).toInt()

            idx = self.idc_combo.currentIndex()
            idc = self.idc_combo.itemData(idx)
            if idc.type() == QtCore.QVariant.Invalid:
                # No item data set -> user entered an IDC
                #idc = int(str(self.idc_combo.itemText(idx)))
                idc = int(self.idc_combo.currentText())
            else:
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

    a = QtGui.QApplication([])
    dialogs = list()
    d = AddDeviceDialog()
    dialogs.append(d)

    d = AddDeviceDialog(bus=1)
    dialogs.append(d)

    d = AddDeviceDialog(available_addresses=[(0,1), (1,1), (0,15), (1,13)])
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
