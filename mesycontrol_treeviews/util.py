#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import logging

def make_logging_source_adapter(module_name, object_instance):
    logger_name = "%s" % (object_instance.__class__.__name__)

    return logging.LoggerAdapter(
            logging.getLogger(logger_name),
            dict(source=id(object_instance)))
