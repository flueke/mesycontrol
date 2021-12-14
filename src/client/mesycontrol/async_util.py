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
__email__  = 'f.lueke@mesytec.com'

import mesycontrol.util as util
from mesycontrol.config_util import GeneratorRunner

class DefaultGeneratorRunner(GeneratorRunner):
    def __init__(self, generator=None, parent_widget=None, parent=None):
        super(DefaultGeneratorRunner, self).__init__(generator, parent)
        self.parent_widget = parent_widget
        self.log = util.make_logging_source_adapter(__name__, self)

    def _object_yielded(self, obj):
        raise ValueError("Error: %s" % obj)
