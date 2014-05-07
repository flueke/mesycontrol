#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtGui
from PyQt4.Qt import Qt
from PyQt4.QtCore import pyqtSlot
from xml.dom import minidom
from xml.etree import ElementTree

from mesycontrol import application_model
from mesycontrol.application_model import DeviceViewModel
from mesycontrol.device_description import DeviceDescription, ParameterDescription
from mesycontrol.config import Config, DeviceConfig, ParameterConfig
from mesycontrol import config_xml
from mesycontrol.device_config_loader import ConfigLoader, ConfigVerifier

class GenericDeviceWidget(QtGui.QWidget):
    def __init__(self, device_model, parent = None):
        super(GenericDeviceWidget, self).__init__(parent)
    
        device_description = application_model.instance.get_device_description_by_idc(device_model.idc)
    
        if device_description is None:
            device_description = DeviceDescription.makeGenericDescription(device_model.idc)
    
        self.device_view_model = DeviceViewModel(device_model, device_description, parent=self)
    
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
            config = config_xml.parse_file(filename)
        except IOError as e:
            QtGui.QMessageBox.critical(self, "Error", "Reading from %s failed: %s" % (filename, e))
            return

        device_model = self.device_view_model.device_model
        idc = device_model.idc

        try:
            new_descr = filter(lambda d: d.idc == idc, config.device_descriptions)[0]
            print "Using first description for idc=", idc
        except IndexError:
            print "No description loaded from config"
            new_descr = None

        possible_configs = filter(lambda cfg: cfg.device_idc == idc, config.device_configs)

        try:
            new_config = possible_configs[0]
            print "Using first config for idc=", idc
        except IndexError:
            print "No device_config loaded from config file"
            new_config = None

        if new_descr is None and new_config is None:
            QtGui.QMessageBox.critical(self, "Error",
                    "No matching device descriptions or device configurations found.")
            return

        if new_descr is None:
            new_descr = application_model.instance.get_device_description_by_idc(idc)
            if new_descr is not None:
                print "Using system device description"

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

    @pyqtSlot()
    def _slt_save_as_button_clicked(self):
        filename = QtGui.QFileDialog.getSaveFileName(self, "Save config as",
                filter="XML files (*.xml);; *")

        if not len(filename):
            return

        device_model = self.device_view_model.device_model
        device_cfg  = DeviceConfig(device_model.idc)
        device_desc = None

        if (self.device_view_model.device_description !=
                application_model.instance.get_device_description_by_idc(device_model.idc)
                and self.device_view_model.device_description !=
                DeviceDescription.makeGenericDescription(device_model.idc)):
            # A non-system/non-default device description needs to be saved
            device_desc = self.device_view_model.device_description

        for param_desc in self.device_view_model.device_description.parameters.values():
            address = param_desc.address
            value   = None
            if not param_desc.read_only:
                value = self.device_view_model.device_model.memory.get(address, None)
            alias   = self.table_widget.item(address, 3).text()
            device_cfg.add_parameter(ParameterConfig(address=address, value=value, alias=alias))

        config = Config()
        config.device_configs.append(device_cfg)
        if device_desc is not None:
            config.device_descriptions.append(device_desc)

        xml_tree   = config_xml.to_etree(config)
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
