#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import pyqtSlot
import logging

class MRCTreeView(QtGui.QWidget):
    sig_open_device_window = pyqtSignal(object)

    def __init__(self, parent=None):
        super(MRCTreeView, self).__init__(parent)
        self.log = logging.getLogger("MRCTreeView")
        self.tree_widget = QtGui.QTreeWidget(self)
        self.tree_widget.setHeaderLabels(['MRC/Bus/Dev', 'IDC', 'RC'])
        self.tree_widget.itemDoubleClicked.connect(self._slt_item_doubleclicked)

        scanbus_button = QtGui.QPushButton("Scanbus")
        scanbus_button.clicked.connect(self._slt_scanbus_button_clicked)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(scanbus_button)
        layout.addWidget(self.tree_widget)
        self.setLayout(layout)

        self.bus_data_complete_mapper = QtCore.QSignalMapper(self)
        self.bus_data_complete_mapper.mapped[QtCore.QObject].connect(self._slt_bus_data_complete)

    @pyqtSlot(object)
    def slt_connection_added(self, connection):
        mrc_model = connection.mrc_model
        self.log.debug("Connection added. MRCModel=%s", str(mrc_model))
        self.bus_data_complete_mapper.setMapping(mrc_model, mrc_model)
        mrc_model.sig_bus_data_complete.connect(self.bus_data_complete_mapper.map)

        mrc_item = QtGui.QTreeWidgetItem()
        mrc_item.setText(0, connection.info_string())
        mrc_item.mrc_model = mrc_model
        self.tree_widget.addTopLevelItem(mrc_item)
        for i in range(3):
            self.tree_widget.resizeColumnToContents(i)
        mrc_item.setExpanded(True)

        for bus in range(2):
            bus_node = QtGui.QTreeWidgetItem()
            bus_node.setText(0, str(bus))
            mrc_item.addChild(bus_node)
            bus_node.setExpanded(True)



    def _slt_bus_data_complete(self, mrc_model):
        f = lambda node: hasattr(node, 'mrc_model') and node.mrc_model == mrc_model
        mrc_node = filter(f, [self.tree_widget.topLevelItem(i) for i in range(self.tree_widget.topLevelItemCount())])[0]

        self.log.debug("MRCModel=%s: scanbus complete. mrc_node=%s", str(mrc_model), str(mrc_node))

        for bus in range(2):
            bus_node     = mrc_node.child(bus)
            bus_children = [bus_node.child(i) for i in range(bus_node.childCount())]

            for dev in range(16):
                if mrc_model.bus_data[bus].get(dev, None) is None:
                    continue

                f = lambda node: hasattr(node, 'device_model') and node.device_model.dev == dev
                try:
                    dev_node = filter(f, bus_children)[0]
                except IndexError:
                    dev_node = None

                if dev_node is None:
                    dev_node = QtGui.QTreeWidgetItem()
                    bus_node.addChild(dev_node)

                dev_node.setText(0, str(dev))
                dev_node.device_model = mrc_model.bus_data[bus][dev]
                dev_node.setText(1, str(dev_node.device_model.idc))
                dev_node.setText(2, "on" if dev_node.device_model.rc else "off")

    def _slt_item_doubleclicked(self, item, column):
        if not hasattr(item, 'device_model'):
            return

        device_model = item.device_model
        mrc_model    = device_model.mrc_model
        bus          = device_model.bus
        dev          = device_model.dev
        rc           = device_model.rc

        if column == 0 or column == 1:
            self.sig_open_device_window.emit(device_model)
        elif column == 2:
            mrc_model.setRc(bus, dev, not rc)
            mrc_model.scanbus(bus)

    def _slt_scanbus_button_clicked(self):
        for mrc_node in  [self.tree_widget.topLevelItem(i) for i in range(self.tree_widget.topLevelItemCount())]:
            mrc_node.mrc_model.scanbus(0)
            mrc_node.mrc_model.scanbus(1)
