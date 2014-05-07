#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from PyQt4 import QtCore
from QtCore import pyqtSignal
from application_model import MRCModel

class AbstractConnection(QtCore.QObject):
    """Abstract MRC connection representation
    Supports the following operations:
    * connect/disconnect
    * queue messages, match request -> response, signal notifications
    * acquire/force/release write access
    * enable/disable silence
    """

    # Connection state
    sig_connecting   = pyqtSignal(str)
    sig_connected    = pyqtSignal(str)
    sig_disconnected = pyqtSignal(str)

    def connect(self):
        raise NotImplemented()

    def disconnect(self):
        raise NotImplemented()

    def is_connected(self):
        raise NotImplemented()

    def get_info_string(self):
        raise NotImplemented()

    # Message queue (most of this is already in TCPClient)
    sig_message_queue_empty = pyqtSignal()
    queue_size, max_queue_size
    queue_message
    sig_message_sent
    sig_message_received
    sig_response_received(request, response)
    sig_notification_received

    # Write access
    has_write_access
    acquire_write_access
    release_write_access
    force_write_access
    write_access_changed
    can_acquire_write_access

    # Silent mode
    is_silenced
    set_silenced
    silence_changed

class VirtualConnection(AbstractConnection):
    """A virtual/simulated MRC connection.
    This is supposed to allow previewing setups without a real MRC being
    present. Note: the bus configuration has to be setup somehow.
    """
    def __init__(self, bus_setup = {}, parent=None):
        super(VirtualConnection, self).__init__(parent)
        self._busses = bus_setup
        self.mrc_model = MRCModel(self, self)

class MesycontrolConnection(AbstractConnection):
    """MRC connection using a mesycontrol_server connection."""
    pass

class LocalMesycontrolConnection(AbstractConnection):
    """MRC connection creating and using its own mesycontrol_server."""
    pass

def factory(**kwargs):
    print kwargs
