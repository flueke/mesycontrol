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
from mesycontrol.device_config_loader import ConfigLoader, ConfigVerifier

class GenericDeviceWidget(QtGui.QWidget):
  def __init__(self, device_model, parent = None):
    super(GenericDeviceWidget, self).__init__(parent)

    self.device_view_model = DeviceViewModel(
          device_model,
          DeviceDescription.makeGenericDescription(device_model.idc),
          parent=self)

    self.device_view_model.sig_parameterRead[int, int].connect(self._slt_parameterUpdated)
    self.device_view_model.sig_parameterSet[int, int].connect(self._slt_parameterUpdated)

    button_layout = QtGui.QHBoxLayout()
    button_layout.addWidget(QtGui.QPushButton("Load", clicked=self._slt_load_button_clicked))
    button_layout.addWidget(QtGui.QPushButton("Save As", clicked=self._slt_save_as_button_clicked))
    
    column_lables = ['Store', 'Address', 'Name', 'Alias', 'Value', 'Set Value',
            'Poll', 'Read-Only', 'Critical', 'Safe Value']

    self.table_widget = QtGui.QTableWidget(256, len(column_lables))
    self.table_widget.verticalHeader().hide()
    self.table_widget.setHorizontalHeaderLabels(column_lables)

    layout = QtGui.QVBoxLayout()
    layout.addLayout(button_layout)
    layout.addWidget(self.table_widget)
    self.setLayout(layout)

    # Create the tablewidget items
    for addr in range(256):
        for col in range(self.table_widget.columnCount()):
            self.table_widget.setItem(addr, col, QtGui.QTableWidgetItem())

    self._populate_tablewidget()

  def set_device_description(self, description):
      self.device_view_model.device_description = description
      self._populate_tablewidget()

  def set_device_config(self, config):
      self.device_view_model.device_config = config
      self._populate_tablewidget()

  def _populate_tablewidget(self):
    device_memory = self.device_view_model.device_model.memory
    device_config = self.device_view_model.device_config
    device_desc   = self.device_view_model.device_description

    try:
        self.table_widget.itemChanged.disconnect(self._slt_table_item_changed)
    except TypeError:
        pass # not connected

    for addr in range(256):
        param_desc   = device_desc.get_parameter_by_address(addr)
        param_config = None if device_config is None else device_config.get_parameter(addr)

        if addr == 8:
            print param_config

        # In Config
        w = self.table_widget.item(addr, 0)
        w.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled)
        w.setCheckState(Qt.Checked if param_desc is not None else Qt.Unchecked)

        # Address
        w = self.table_widget.item(addr, 1)
        w.setFlags(Qt.ItemIsEnabled)
        w.setText(str(addr))

        # Name
        w = self.table_widget.item(addr, 2)
        if param_desc is not None and param_desc.name is not None:
           w.setText(param_desc.name)
        else:
           w.setText("")

        # Alias
        w = self.table_widget.item(addr, 3)
        if param_config is not None and param_config.alias is not None:
           w.setText(param_config.alias)
        else:
           w.setText("")

        # Value
        w = self.table_widget.item(addr, 4)
        w.setFlags(Qt.ItemIsEnabled)
        if device_memory.has_key(addr):
           w.setText(str(device_memory[addr]))
        else:
           w.setText("")

        # Set Value
        w = self.table_widget.item(addr, 5)
        w.setFlags(Qt.ItemIsEnabled)
        if param_desc is None or not param_desc.read_only:
           w.setFlags(Qt.ItemIsEnabled|Qt.ItemIsEditable)
           #if param_config is not None and param_config.value is not None:
           #    w.setText(str(param_config.value))

        # Poll
        w = self.table_widget.item(addr, 6)
        w.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled)
        w.setCheckState(Qt.Checked if param_desc is not None and param_desc.poll else Qt.Unchecked)

        # Read-Only
        w = self.table_widget.item(addr, 7)
        w.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled)
        w.setCheckState(Qt.Checked if param_desc is not None and param_desc.read_only else Qt.Unchecked)

        # Critical
        w = self.table_widget.item(addr, 8)
        w.setFlags(Qt.ItemIsUserCheckable|Qt.ItemIsEnabled)
        w.setCheckState(Qt.Checked if param_desc is not None and param_desc.critical else Qt.Unchecked)

        # Safe Value
        w = self.table_widget.item(addr, 9)
        w.setFlags(Qt.ItemIsEnabled)
        if param_desc is not None and param_desc.critical:
           w.setFlags(Qt.ItemIsEnabled|Qt.ItemIsEditable)
           w.setText(str(param_desc.safe_value))
        else:
           w.setText("")

        if param_desc is not None and addr not in device_memory:
           self.device_view_model.device_model.readParameter(addr)

    self.table_widget.resizeColumnsToContents()
    self.table_widget.resizeRowsToContents()

    self.table_widget.itemChanged.connect(self._slt_table_item_changed)

  @pyqtSlot()
  def _slt_load_button_clicked(self):
      filename = QtGui.QFileDialog.getOpenFileName(self, "Open config file",
              filter="XML files (*.xml);; *")
        
      if not len(filename):
          return

      try:
          descriptions, configs = DeviceConfigXML.parse_file(filename)
      except IOError as e:
          QtGui.QMessageBox.critical(self, "Error", "Reading from %s failed: %s" % (filename, e))
          return

      print "Read", len(descriptions), "descriptions and", len(configs), "configs"

      device_model = self.device_view_model.device_model
      idc = device_model.idc
      bus = device_model.bus
      dev = device_model.dev

      try:
          new_descr = filter(lambda d: d.idc == idc, descriptions)[0]
      except IndexError:
          new_descr = None


      try:
          new_config = filter(lambda cfg: cfg.get_bus_number() == bus and cfg.get_device_number() == dev,
                  configs)[0]
      except IndexError:
          new_config = None

      if new_descr is None and new_config is None:
          QtGui.QMessageBox.critical(self, "Error",
                  "No matching device descriptions or device configurations found.")
          return

      if new_descr is None:
          print "No Device Description loaded. Using generic description"
          new_descr = DeviceDescription.makeGenericDescription(device_model.idc)

      self.set_device_description(new_descr)
      print "New Device Description loaded"

      if new_config is not None:
          self.set_device_config(new_config)
          print "New Device Configuration applied to GUI"
          self._config_loader = ConfigLoader(device_model, new_config, new_descr)
          self._config_loader.sig_complete.connect(self._slt_config_loader_complete)
          self._config_loader.start()
      else:
          print "No configs to load"

      # Loading and verifying
      # - Find a config with bus and dev matching this device
      #   (TODO: let the user choose a config from the file and ignore bus,dev,idc mismatches)
      # - Find a description matching this devices IDC
      # - Update the table using the description
      # - Update aliases using the configuration
      # - Load the configuration:
      #   * Build a list of parameters to set
      #     - Critical params with safe-values first
      #     - Other params
      #     - Critical params with config values
      #   * Set each of the parameters in the list
      # - Verify the configuration:
      #   For each param in the config assert actual value == config value
      # - Also needed:
      #   * Updating of the poll set for this device:
      #     Remove any poll parameters, load config, add poll parameters from description

      # Loading a complete setup:
      # For each config loaded:
      #   Find a matching device by comparing (mrc, bus, dev)
      #   Load the config as described above
      #   Generic Device Widgets need to be updated somehow to reflect alias changes etc.
      #   Tree View needs to be updated to reflect changes to MRC aliases

      # XXX: The idea with multiple DeviceDescriptions is not that easy to
      # represent in the GUI. On loading a complete setup should existing
      # GenericWidgets use the newly loaded description or continue using the
      # existing one? If for some device there are multiple descriptions with
      # different poll sets which one should be used? Should they be merged? If
      # so I'd need to keep track which DeviceViewModel added a certain param.
      # So maybe there should be only one DeviceViewModel per DeviceModel. This
      # single model could be updated with the latest loaded description.
      # Concurrently opened specialized device widgets should still use their
      # own device description as they might rely on parameter names (that is
      # the main reason to have descriptions after all).

  @pyqtSlot()
  def _slt_save_as_button_clicked(self):
      filename = QtGui.QFileDialog.getSaveFileName(self, "Save config as",
             filter="XML files (*.xml);; *")

      if not len(filename):
         return

      cfg = DeviceConfig()
      cfg.mrc_address   = self.device_view_model.device_model.mrc_model.get_mrc_address_string()
      cfg.bus_number    = self.device_view_model.device_model.bus
      cfg.device_number = self.device_view_model.device_model.dev

      if self.device_view_model.device_description != \
          DeviceDescription.makeGenericDescription(self.device_view_model.device_model.idc):
          # A non-default device description needs to be saved
          cfg.device_description = self.device_view_model.device_description

      for param_desc in self.device_view_model.device_description.parameters.values():
          address = param_desc.address
          value   = None
          if not param_desc.read_only:
              value = self.device_view_model.device_model.memory.get(address, None)
          alias   = self.table_widget.item(address, 3).text()
          cfg.add_parameter(ParameterConfig(address=address, value=value, alias=alias))

      out_objects = [cfg]
      if cfg.device_description is not None:
          out_objects.append(cfg.device_description)

      xml_tree   = DeviceConfigXML.to_etree(out_objects)
      xml_string = ElementTree.tostring(xml_tree.getroot())
      xml_string = minidom.parseString(xml_string).toprettyxml(indent='  ')

      try:
          with open(filename, 'w') as f:
             f.write(xml_string)
      except IOError as e:
          QtGui.QMessageBox.critical(self, "Error", "Writing to %s failed: %s" % (filename, e))
      else:
          QtGui.QMessageBox.information(self, "Info", "Configuration written to %s" % filename)

  def _slt_parameterUpdated(self, addr, value):
      #print "_slt_parameter_value_updated", addr, value
      self.table_widget.item(addr, 4).setText(str(value))

  def _slt_table_item_changed(self, item):
      #print "_slt_table_item_changed"
      addr       = item.row()
      param_desc = self.device_view_model.device_description.get_parameter_by_address(addr)

      # "In Config" Checkbox
      if item.column() == 0:
         if item.checkState() == Qt.Checked:
             name       = str(self.table_widget.item(addr, 2).text()).strip()
             poll       = self.table_widget.item(addr, 6).checkState() == Qt.Checked
             read_only  = self.table_widget.item(addr, 7).checkState() == Qt.Checked 
             critical   = self.table_widget.item(addr, 8).checkState() == Qt.Checked 
             try:
                 safe_value = int(str(self.table_widget.item(addr, 9).text()).strip())
             except ValueError:
                 safe_value = 0

             param_desc            = ParameterDescription(addr)
             param_desc.name       = name if len(name) else None
             param_desc.poll       = poll
             param_desc.read_only  = read_only
             param_desc.critical   = critical
             param_desc.safe_value = safe_value
             self.device_view_model.device_description.add_parameter(param_desc)
             if poll:
                 self.device_view_model.device_model.addPollParameter(addr)
             else:
                 self.device_view_model.device_model.removePollParameter(addr)

         else:
             self.device_view_model.device_description.del_parameter(param_desc)
             self.device_view_model.device_model.removePollParameter(addr)

      # Name
      elif item.column() == 2 and param_desc is not None:
          name = str(item.text()).strip()
          param_desc.name = name if len(name) else None
      # Alias
      elif item.column() == 3:
         pass # The alias is only used when saving a DeviceConfig
      # Set Value
      elif item.column() == 5:
         try:
             int_val = int(str(item.text()).strip())
             if 0 <= int_val and int_val <= 65535:
                 self.device_view_model.setParameter(addr, int_val)
         except ValueError:
             item.setText("")
      # Poll
      elif item.column() == 6 and param_desc is not None:
         param_desc.poll = item.checkState() == Qt.Checked
         if param_desc.poll:
             self.device_view_model.device_model.addPollParameter(item.row())
         else:
             self.device_view_model.device_model.removePollParameter(item.row())
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

  def _slt_config_loader_complete(self, result):
      if result:
        print "Config loaded successfully. Verifying"
        self._config_verifier = ConfigVerifier(
                self._config_loader.device_model,
                self._config_loader.device_config,
                self._config_loader.device_description)
        self._config_verifier.sig_complete.connect(self._slt_config_verifier_complete)
        self._config_verifier.start()
      else:
        print "Config loading failed"
      self._config_loader = None

  def _slt_config_verifier_complete(self, result):
      if result:
          print "Config verified successfully!"
      else:
          print "Config verification failed!"
          print "Failed param: %d=%d should be %d" % self._config_verifier.failed_param
      self._config_verifier = None
