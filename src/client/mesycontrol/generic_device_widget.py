#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtGui
from PyQt4.Qt import Qt

class GenericDeviceWidget(QtGui.QWidget):
  def __init__(self, device_model, parent = None):
    super(GenericDeviceWidget, self).__init__(parent)
    self.device_model = device_model
    self.device_model.sig_parameterRead.connect(self._slt_parameter_value_updated)
    self.device_model.sig_parameterSet.connect(self._slt_parameter_value_updated)

    self.table_widget = QtGui.QTableWidget(256, 3)
    self.table_widget.setHorizontalHeaderLabels(['Address', 'Value', 'Set Value'])
    self.table_widget.verticalHeader().hide()
    layout = QtGui.QHBoxLayout()
    layout.addWidget(self.table_widget)
    self.setLayout(layout)

    device_memory = self.device_model.memory

    for addr in range(256):
      self.table_widget.setItem(addr, 0, QtGui.QTableWidgetItem(str(addr)))
      self.table_widget.item(addr, 0).setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)

      self.table_widget.setItem(addr, 1, QtGui.QTableWidgetItem())
      self.table_widget.item(addr, 1).setFlags(Qt.ItemIsSelectable|Qt.ItemIsUserCheckable|Qt.ItemIsEnabled)
      self.table_widget.item(addr, 1).setCheckState(Qt.Unchecked)

      self.table_widget.setItem(addr, 2, QtGui.QTableWidgetItem())

      if device_memory.has_key(addr):
        self.table_widget.item(addr, 1).setText(str(device_memory[addr]))
        self.table_widget.item(addr, 2).setText(str(device_memory[addr]))

    self.table_widget.resizeColumnsToContents()
    self.table_widget.resizeRowsToContents()

    self.table_widget.itemChanged.connect(self._slt_table_item_changed)

    for addr in range(256):
      if not device_memory.has_key(addr):
          self.device_model.readParameter(addr)

  def _slt_parameter_value_updated(self, addr, value):
      print "_slt_parameter_value_updated", addr, value
      self.table_widget.item(addr, 1).setText(str(value))

  def _slt_table_item_changed(self, item):
    if item.column() == 1:
      if item.checkState() == Qt.Checked:
        self.device_model.addPollParameter(item.row())
      else:
        self.device_model.removePollParameter(item.row())

    elif item.column() == 2:
      try:
        int_val = int(item.text())
        if 0 <= int_val and int_val <= 65535:
            self.device_model.setParameter(item.row(), int_val)
      except ValueError:
          pass
