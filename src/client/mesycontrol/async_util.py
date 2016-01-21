#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from config_util import GeneratorRunner

class DefaultGeneratorRunner(GeneratorRunner):
    def __init__(self, generator=None, parent_widget=None, parent=None):
        super(DefaultGeneratorRunner, self).__init__(generator, parent)
        self.parent_widget = parent_widget

    def _object_yielded(self, obj):
        raise ValueError("Error: %s" % obj)
