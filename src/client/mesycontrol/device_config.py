#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

class DeviceConfig(object):
    def __init__(self):
        #: Optional name of a device description or a DeviceDescription instance or None.
        self.device_description = None  

        #: Optional path to a file containing the device description to use.
        #: self.device_description has precendence over this setting.
        self.device_description_file = None

        #: Optional user defined alias for this device.
        self.alias = None

        #: Optional mrc address specification.
        #: Format is: <dev>@<baud> or <host>:<port>.
        #: If specified this setting can enable auto-starting of a mesycontrol
        #: server connecting to the given mrc.
        self.mrc_address = None

        #: Optional address of a mesycontrol server to connect to.
        #: Format is <host>:<port>.
        self.mesycontrol_server = None

        #: Optional bus number of the device.
        self.bus_number = None

        #: Optional device number on the bus.
        self.device_number = None

        #: The list of ParameterConfig objects containing the actual
        #: parameter values.
        self.parameters = []

class ParameterConfig(object):
    def __init__(self):
        self.address = None #: Numeric address or parameter description name
        self.alias   = None #: Optional user defined alias for the parameter.
        self.value   = None #: The parameters unsigned short value.

# Where to store aliases for MRCs? Probably in the clients connection list.
# Then MRC aliases could be used in device configurations instead of some kind
# of address specification (e.g. device config references "my_mrc1" and the
# client contains a mrc connection with that name => mrc name from config can
# be resolved). The mrc connection list should also be exportable!

# Mesycontrol (XML) file contents:
# * Zero or more device descriptions
# * Zero or more device configurations
# * At least one of the above must be present
# * An optional file description
# * The device configurations may reference file-internal device descriptions,
#   built-in device descriptions and possibly filenames containing device
#   descriptions.
#
# * A device configuration may include an mrc identifier plus bus and device
#   numbers (basically a full device address) to enable automatic loading of a
#   setup. If no device address is given the user must be asked for one.
#   Using the full device address together with device descriptions enables
#   verifying of device IDCs when loading a configuration (is the device
#   present? does it have the correct IDC?)
# * Loading of a device configuration:
#   Parameters are written to the device in the order they're declared in the
#   description file. If no description is present (just raw param -> value
#   entries in the config) the order of parameters is used instead.
#   TODO (later): How to specify a load order for generic devices when
#   creating a generic device description via the generic device widget? For
#   now the file could just be hand-edited.
# * TODO: How to test for certain firmware versions? E.g. MSCF16 submodels?
# * IDC is the same but the contents of a certain parameter (the firmware
#   revision) differ.
#   Two scenarios for this:
#     - Use a single device description with submodel specific parameters.
#     - Write multiple device descriptions with each one specifying which
#       firmware revision it expects.
