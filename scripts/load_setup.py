#!/usr/bin/env python
# -*- coding: utf-8 -*-

from mesycontrol.script import *
from mesycontrol import config_xml, setup

def print_progress(cur, tot):
    print "Loading setup (step %d/%d)" % (cur, tot)

if len(sys.argv) < 2:
    print "Usage: %s <setup_file>" % sys.argv[0]
    print "Example: %s ~/my-setup.xml" % sys.argv[0]
    sys.exit(1)

with get_script_context() as ctx:
    print "Loading setup from %s" % sys.argv[1]

    cfg = config_xml.parse_file(sys.argv[1])

    print ("Setup contents: %d connections, %d device configs, %d device descriptions" %
            (len(cfg.connection_configs), len(cfg.device_configs), len(cfg.device_descriptions)))
    for dev_cfg in cfg.device_configs:
        print "Device Config: idc=%d, len(params)=%d" % (dev_cfg.device_idc, len(dev_cfg.get_parameters()))

    setup_loader = setup.SetupLoader(cfg)
    setup_loader.progress_changed.connect(print_progress)
    setup_loader() # Execute the setup loader

    print "SetupLoader results: ", setup_loader.is_complete(), setup_loader.has_failed(), setup_loader.get_result()

    print "Setup loaded. Current connections:"

    for conn in ctx.app_model.mrc_connections:
        print " "*2, conn.get_info()
        mrc = MRCWrapper(conn.mrc_model)
        for i in range(2):
            print " "*4, mrc[i]
