#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2016 mesytec GmbH & Co. KG <info@mesytec.com>
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
__email__  = 'florianlueke@gmx.net'

from PyQt4 import QtCore, QtGui
import logging
import signal
import sys

def signal_handler(signum, frame):
    logging.info("Received signal %s. Quitting...",
            signal.signum_to_name.get(signum, "%d" % signum))
    QtGui.QApplication.quit()

def test_app_model_using_local_setup():
    from mesycontrol import application_registry
    from mesycontrol import app_model
    from mesycontrol import config
    from mesycontrol import hw_model
    from mesycontrol import mrc_connection
    from mesycontrol import mrc_controller

    logging.basicConfig(level=logging.INFO,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    signal.signum_to_name = dict((getattr(signal, n), n)
            for n in dir(signal) if n.startswith('SIG') and '_' not in n)
    signal.signal(signal.SIGINT, signal_handler)

    application_registry.instance = application_registry.ApplicationRegistry(
            sys.executable if getattr(sys, 'frozen', False) else __file__)

    app = QtGui.QApplication(sys.argv)

    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    con                             = mrc_connection.factory(serial_port='/dev/ttyUSB0', baud_rate=0)
    mrc_model                       = hw_model.MRCModel()
    mrc_model.controller            = mrc_controller.MRCController(con, mrc_model)
    mrc_config                      = config.MRCConfig()
    mrc_config.connection_config    = config.make_connection_config(con)
    mrc                             = app_model.MRC(mrc_model=mrc_model, mrc_config=mrc_config)
    setup                           = config.Setup()
    setup.add_mrc_config(mrc_config)

    def on_mrc_connecting():
        print "connecting..."

    def on_mrc_connected():
        print "connected!"

    def on_mrc_disconnected(info=None):
        print "disconnected!", info

    def on_mrc_ready():
        print "MRC is ready!"
        for device in mrc.get_devices():
            print device, device.model, device.config

        print "Saving setup..."

    def on_device_added(device):
        print "Device added: %s" % device

    mrc.connecting.connect(on_mrc_connecting)
    mrc.connected.connect(on_mrc_connected)
    mrc.disconnected.connect(on_mrc_disconnected)
    mrc.ready.connect(on_mrc_ready)
    mrc.device_added.connect(on_device_added)

    mrc.connect()

    return app.exec_()

test_app_model_using_local_setup.__test__ = False # make nose ignore this function

if __name__ == "__main__":
    test_app_model_using_local_setup()
