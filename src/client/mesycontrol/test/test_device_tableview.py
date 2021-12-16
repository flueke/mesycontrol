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

from mesycontrol.device_tableview import *
from mesycontrol.hardware_model import *

def test_simple():
    app = QtGui.QApplication([])

    device_model = DeviceModel(bus=0, address=1, idc=17, rc=True)
    for i in range(256):
        device_model.set_parameter(i, i)
    device       = Device(device_model)
    table_model  = DeviceTableModel(device)
    table_view   = DeviceTableView(table_model)

    def on_button_triggered():
        for i in range(256):
            device_model.set_parameter(i, 
                    device_model.get_parameter(i) + 1)

    def on_set_device_button_triggered():
        table_model.device = device

    button1 = QtGui.QPushButton("set parameters", clicked=on_button_triggered)
    button2 = QtGui.QPushButton("set device", clicked=on_set_device_button_triggered)

    layout = QtGui.QHBoxLayout()
    layout.addWidget(table_view)
    layout.addWidget(button1)
    layout.addWidget(button2)

    w = QtGui.QWidget()
    w.setLayout(layout)
    w.show()

    return app.exec_()

test_simple.__test__ = False # Make nose ignore this function

if __name__ == "__main__":
    test_simple()
