#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

"""Reading and writing mesycontrol config files."""

# <mesycontrol type="setup">
#   description
#   list of mrc configs
#       list of device configs
#   list of device profiles
# </mesycontrol>

# <mesycontrol type="deviceconfig">
#   device attributes here (name, bus, address, idc)
#   list of parameter configs
#   list of extensions
#   device profile
# </mesycontrol>

from xml.dom import minidom
from xml.etree import ElementTree
from xml.etree.ElementTree import TreeBuilder

class CommentTreeBuilder(TreeBuilder):
    def comment(self, data):
        self.start(ElementTree.Comment, {})
        self.data(data)
        self.end(ElementTree.Comment)
