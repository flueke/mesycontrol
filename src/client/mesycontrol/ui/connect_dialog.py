#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore, QtGui, uic
from PyQt4.QtCore import pyqtSlot
from mesycontrol import application_registry
from mesycontrol import config
from mesycontrol import util

class ConnectDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        super(ConnectDialog, self).__init__(parent)

        #uic.loadUi(resource_stream('mesycontrol.ui', 'connect_dialog.ui'), self)
        uic.loadUi(application_registry.instance.find_data_file('mesycontrol/ui/connect_dialog.ui'), self)
        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(False)
        self.combo_serial_port.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+'), None))
        self.le_tcp_host.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+'), None))
        self.le_mesycontrol_host.setValidator(QtGui.QRegExpValidator(QtCore.QRegExp('.+'), None))
        self.le_tcp_host.setText('localhost')
        self.le_mesycontrol_host.setText('localhost')

        for port in util.list_serial_ports():
            self.combo_serial_port.addItem(port)

        for le in self.findChildren(QtGui.QLineEdit):
            le.textChanged.connect(self._validate_inputs)

        for combo in self.findChildren(QtGui.QComboBox):
            combo.currentIndexChanged.connect(self._validate_inputs)
            combo.editTextChanged.connect(self._validate_inputs)

        self.stacked_widget.currentChanged.connect(self._validate_inputs)
        self._validate_inputs()

    @pyqtSlot()
    def _validate_inputs(self):
        page_widget = self.stacked_widget.currentWidget()
        is_ok       = True

        for le in page_widget.findChildren(QtGui.QLineEdit):
            is_ok = is_ok and le.hasAcceptableInput()

        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(is_ok)

    @pyqtSlot()
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

