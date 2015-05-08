#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

# Purpose: Create and test two tree views needed for mesycontrol: the hardware
# tree and the setup tree. Both trees will be shown side by side and must be
# kept in sync (selections, item positions, react to item
# changes/adds/removes/...)

# Components:
# QAbstractItemModels: HardwareTreeModel, SetupTreeModel
# QTreeViews: HardwareTreeView, SetupTreeView
# TreeViewDirector: updates models
# TreeViewWidget: combines HardwareTreeView and SetupTreeView into one Widget

# Context Menu handling is external (MCTreeView)
# Selection Sync is external (MCTreeView)
# Sync of nodes is external (MCTreeView)
# how to handle changes to nodes?
# each specific node type knows when its' ref changes
# -> call a notify_changed method on the model

from qt import QtCore
from qt import QtGui
from qt import Qt

import setup_tree_model as stm
from setup_tree_view import SetupTreeView

import signal
import sys

## Setup/Config side
#class Setup:
#    def __init__(self):
#        self._mrc_configs = list()
#
#class MRCConfig:
#    def __init__(self):
#        self._devices = list()
#
#class DeviceConfig:
#    # bus, address could be changed by the user. in this case
#    # someone has to check the consistency of the tree structures. the combined
#    # model might have to be updated.
#    def __init__(self, bus, address):
#        self._parameters = dict()
#
#class ParameterConfig:
#    def __init__(self, address, value=None):
#        self._address = address
#        self._value   = value
#
#s = Setup()
## ...
#future = s.get_mrc("/dev/ttyUSB0").get_device(0, 1).get_parameter(2)
#future = s["/dev/ttyUSB0"][0][1][2]

## Hardware side
#class Connections:
#    def __init__(self):
#        self._mrcs = list()
#
#    def add_mrc(self, mrc):
#    def remove_mrc(self, mrc):
#    def get_mrc(self, url):
#
#class MRC:
#    def __init__(self):
#        self._devices = list()
#
#    def add_device(self, device):
#    def remove_device(self, device):
#    def get_device(self, bus, address):
#
#class Device:
#    pass
#
#class Parameter:
#    def __init__(self, address, value=None):
#        self._address = address
#        self._value   = value
#
#c = Connections()
## ...
#future = c.get_mrc("/dev/ttyUSB0").get_device(0, 1).get_parameter(2)
#future = c["/dev/ttyUSB0"][0][1][2]

## Combined Model
#class Root:
#    def __init__(self):
#        self._setup = None
#        self._connections = None
#
#class MRC:
#    # condition: config.url == hardware.url
#    def __init__(self):
#        self._config = None
#        self._hardware = None
#
#class Device:
#    # condition: (config.bus, config.address) == (hardware.bus, hardware.address)
#    def __init__(self):
#        self._config = None
#        self._hardware = None
#
#class MRCCollection:
#    def add_mrc(self, mrc)
#    def remove_mrc(self, mrc)
#    def get_mrc(self, url)
#
#class BasicMRC:
#    def __init__(self, url):
#        self._url = url
#        self._devices = dict()
#
#    def get_url(self):
#        return self._url
#
#    def add_device(self, device):
#        if (device.bus, device.address) in self._devices:
#            raise DuplicateDevice()
#        self._devices[(device.bus, device.address)] = device
#        device.set_mrc(self)
#
#    def remove_device(self, device):
#    def get_device(self, bus, address):
#
#class BasicDevice:
#    def __init__(self, bus, address):
#        self._bus = bus
#        self._address = address

# True for both sides:
# - MRC is identified by its connection URL
# - Bus is identified by its number
# - Device is identified by its (bus, address) pair
# - Parameter is identified by its address
# - The root (Setup, Connections) contains unique MRCs. Duplicates are not allowed
# - Each MRC contains unique devices. No duplicates allowed.

def signal_handler(signum, frame):
    QtGui.QApplication.quit()

import app_model as am
import basic_model as bm
import hardware_model as hm
import setup_model as sm

if __name__ == "__main__":
    QtGui.QApplication.setDesktopSettingsAware(False)
    app = QtGui.QApplication(sys.argv)
    app.setStyle(QtGui.QStyleFactory.create("Plastique"))

    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)

    signal.signal(signal.SIGINT, signal_handler)

    import pyqtgraph as pg
    import pyqtgraph.console

    console = pg.console.ConsoleWidget(namespace=locals())
    console.show()

    hw_registry    = bm.MRCRegistry()


    setup_registry = sm.Setup()

    app_director   = am.Director(hw_registry, setup_registry)

    hw_registry.add_mrc(hm.MRC("serial:///dev/ttyUSB0"))
    setup_registry.add_mrc(sm.MRC("mc://localhost:4001"))
    setup_registry.add_mrc(sm.MRC("serial:///dev/ttyUSB0"))

    print "hw:", hw_registry.mrcs
    print "setup:", setup_registry.mrcs
    print "app:", app_director.registry.mrcs

    for mrc in app_director.registry.mrcs:
        print str(mrc), "hw:", str(mrc.hw), "cfg:", str(mrc.cfg)

    print

    for mrc in hw_registry.mrcs:
        hw_registry.remove_mrc(mrc)

    print "hw:", hw_registry.mrcs
    print "setup:", setup_registry.mrcs
    print "app:", app_director.registry.mrcs

    for mrc in app_director.registry.mrcs:
        print str(mrc), "hw:", str(mrc.hw), "cfg:", str(mrc.cfg)

    print

    for mrc in setup_registry.mrcs:
        setup_registry.remove_mrc(mrc)

    print "hw:", hw_registry.mrcs
    print "setup:", setup_registry.mrcs
    print "app:", app_director.registry.mrcs

    for mrc in app_director.registry.mrcs:
        print str(mrc), "hw:", str(mrc.hw), "cfg:", str(mrc.cfg)


    ret = app.exec_()
    sys.exit(ret)
