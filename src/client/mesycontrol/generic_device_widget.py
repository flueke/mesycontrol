#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtGui
from PyQt4.Qt import Qt
from PyQt4.QtCore import pyqtSlot
from xml.dom import minidom
from xml.etree import ElementTree

from mesycontrol.application_model import DeviceViewModel
from mesycontrol.device_description import DeviceDescription, ParameterDescription
from mesycontrol.device_config import DeviceConfig, ParameterConfig
from mesycontrol.device_config_xml import DeviceConfigXML

def make_generic_device_description(idc, name=None):
   ret = DeviceDescription()
   ret.idc  = idc
   ret.name = name

   for i in range(256):
      param_desc = ParameterDescription()
      param_desc.address = i
      ret.add_parameter(param_desc)

   return ret

class GenericDeviceWidget(QtGui.QWidget):
  def __init__(self, device_model, parent = None):
    super(GenericDeviceWidget, self).__init__(parent)

    self.device_view_model = DeviceViewModel(
          device_model,
          make_generic_device_description(device_model.idc, "Generic Device"),
          parent=self)

    self.device_view_model.sig_parameterRead[int, int].connect(self._slt_parameterUpdated)
    self.device_view_model.sig_parameterSet[int, int].connect(self._slt_parameterUpdated)

    button_layout = QtGui.QHBoxLayout()
    load_from = QtGui.QPushButton("Load")
    save_as   = QtGui.QPushButton("Save As")
    load_from.clicked.connect(self._slt_load_button_clicked)
    save_as.clicked.connect(self._slt_save_as_button_clicked)
    button_layout.addWidget(load_from)
    button_layout.addWidget(save_as)

    self.table_widget = QtGui.QTableWidget(256, 10)
    self.table_widget.setHorizontalHeaderLabels(
          ['In Config', 'Address', 'Name', 'Alias', 'Value', 'Set Value', 'Poll', 'Read-Only', 'Critical', 'Safe Value'])
    self.table_widget.verticalHeader().hide()
    layout = QtGui.QVBoxLayout()
    layout.addLayout(button_layout)
    layout.addWidget(self.table_widget)
    self.setLayout(layout)

    device_memory = self.device_view_model.device_model.memory
    device_config = self.device_view_model.device_config

    for addr in range(256):
       param_desc   = self.device_view_model.device_description.get_parameter_by_address(addr)
       param_config = None if device_config is None else device_config.get_parameter(addr)
       widgets = []

       # In Config
       w = QtGui.QTableWidgetItem()
       w.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled)
       w.setCheckState(Qt.Checked if param_desc is not None else Qt.Unchecked)
       widgets.append(w)

       # Address
       w = QtGui.QTableWidgetItem(str(addr))
       w.setFlags(Qt.ItemIsEnabled)
       widgets.append(w)

       # Name
       w = QtGui.QTableWidgetItem()
       if param_desc is not None and param_desc.name is not None:
          w.setText(param_desc.name)
       widgets.append(w)

       # Alias
       w = QtGui.QTableWidgetItem()
       if param_config is not None and param_config.alias is not None:
          w.setText(param_config.alias)
       widgets.append(w)

       # Value
       w = QtGui.QTableWidgetItem()
       w.setFlags(Qt.ItemIsEnabled)
       if device_memory.has_key(addr):
          w.setText(str(device_memory[addr]))
       widgets.append(w)

       # Set Value
       w = QtGui.QTableWidgetItem()
       w.setFlags(Qt.ItemIsEnabled)
       if param_desc is None or not param_desc.read_only:
          w.setFlags(Qt.ItemIsEnabled|Qt.ItemIsEditable)
       widgets.append(w)

       # Poll
       w = QtGui.QTableWidgetItem()
       w.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled)
       w.setCheckState(Qt.Checked if param_desc is not None and param_desc.poll else Qt.Unchecked)
       widgets.append(w)

       # Read-Only
       w = QtGui.QTableWidgetItem()
       w.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled)
       w.setCheckState(Qt.Checked if param_desc is not None and param_desc.read_only else Qt.Unchecked)
       widgets.append(w)

       # Critical
       w = QtGui.QTableWidgetItem()
       w.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled)
       w.setCheckState(Qt.Checked if param_desc is not None and param_desc.critical else Qt.Unchecked)
       widgets.append(w)

       # Safe Value
       w = QtGui.QTableWidgetItem()
       w.setFlags(Qt.ItemIsEnabled)
       if param_desc is not None and param_desc.critical:
          w.setFlags(Qt.ItemIsEnabled|Qt.ItemIsEditable)
          w.setText(str(param_desc.safe_value))
       widgets.append(w)

       for i, w in enumerate(widgets):
          self.table_widget.setItem(addr, i, w)

       if param_desc is not None and addr not in device_memory:
          self.device_view_model.device_model.readParameter(addr)

    self.table_widget.resizeColumnsToContents()
    self.table_widget.resizeRowsToContents()

    self.table_widget.itemChanged.connect(self._slt_table_item_changed)

  @pyqtSlot()
  def _slt_load_button_clicked(self):
     filename = QtGui.QFileDialog.getOpenFileName(self, "Open config file")

     if not len(filename):
        return

     descriptions, configs = DeviceConfigXML.parse_file(filename)
     print "Read", len(descriptions), "descriptions and", len(configs), "configs"

  @pyqtSlot()
  def _slt_save_as_button_clicked(self):
      filename = QtGui.QFileDialog.getSaveFileName(self, "Save config as")

      if not len(filename):
         return

      cfg = DeviceConfig()
      cfg.device_description = self.device_view_model.device_description
      for param_desc in self.device_view_model.device_description.parameters:
         address = param_desc.name if param_desc.name is not None else param_desc.address
         value   = self.device_view_model.device_model.memory.get(param_desc.address, None) if not param_desc.read_only else None
         alias   = self.table_widget.item(param_desc.address, 3).text()
         cfg.add_parameter(ParameterConfig(address=address, value=value, alias=alias))

      xml_tree   = DeviceConfigXML.to_etree([self.device_view_model.device_description, cfg])
      xml_string = ElementTree.tostring(xml_tree.getroot())
      xml_string = minidom.parseString(xml_string).toprettyxml(indent='  ')

      with open(filename, 'w') as f:
         f.write(xml_string)

  def _slt_parameterUpdated(self, addr, value):
      print "_slt_parameter_value_updated", addr, value
      self.table_widget.item(addr, 4).setText(str(value))

  def _slt_table_item_changed(self, item):
      print "_slt_table_item_changed"
      addr       = item.row()
      param_desc = self.device_view_model.device_description.get_parameter_by_address(addr)

      # In Config
      if item.column() == 0:
         if item.checkState() == Qt.Checked:
            param_desc            = ParameterDescription()
            param_desc.addr       = addr
            param_desc.name       = self.table_widget.item(addr, 2).text()
            param_desc.poll       = self.table_widget.item(addr, 6).checkState() == Qt.Checked
            param_desc.read_only  = self.table_widget.item(addr, 7).checkState() == Qt.Checked 
            param_desc.critical   = self.table_widget.item(addr, 8).checkState() == Qt.Checked 
            param_desc.safe_value = self.table_widget.item(addr, 9).text()
            self.device_view_model.device_description.add_parameter(param_desc)
         else:
            self.device_view_model.device_description.del_parameter(param_desc)

      # Name
      elif item.column() == 2 and param_desc is not None:
         param_desc.name = item.text()
      # Alias
      elif item.column() == 3:
         pass
      # Set Value
      elif item.column() == 5:
         try:
            int_val = int(item.text())
            if 0 <= int_val and int_val <= 65535:
               self.device_view_model.setParameter(addr, int_val)
         except ValueError:
            item.setText("")
      # Poll
      elif item.column() == 6 and param_desc is not None:
         param_desc.poll = item.checkState() == Qt.Checked
      # Read-Only
      elif item.column() == 7 and param_desc is not None:
         param_desc.read_only = item.checkState() == Qt.Checked
         self.table_widget.item(addr, 5).setFlags(Qt.ItemIsEnabled)
         if not param_desc.read_only:
            self.table_widget.item(addr, 5).setFlags(Qt.ItemIsEnabled|Qt.ItemIsEditable)
      # Critical
      elif item.column() == 8 and param_desc is not None:
         param_desc.critical = item.checkState() == Qt.Checked
         self.table_widget.item(addr, 9).setFlags(Qt.ItemIsEnabled)
         if param_desc.critical:
            self.table_widget.item(addr, 9).setFlags(Qt.ItemIsEnabled|Qt.ItemIsEditable)
      # Safe Value
      elif item.column() == 9 and param_desc is not None:
         try:
            int_val = int(item.text())
            if 0 <= int_val and int_val <= 65535:
               param_desc.safe_value = int_val
         except ValueError:
            item.setText("")
