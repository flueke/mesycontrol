#!/usr/bin/env python
# -*- coding: utf-8 -*-

from mesycontrol.script import *
from mesycontrol import config
from mesycontrol import config_xml

def print_progress(cur, tot):
    print "Loading setup (step %d/%d)" % (cur, tot)

if len(sys.argv) < 2:
    print "Usage: %s <setup_file>" % sys.argv[0]
    print "Example: %s ~/my-setup.xml" % sys.argv[0]
    sys.exit(1)

with get_script_context() as ctx:
    print "Loading setup from %s:" % sys.argv[1]

    setup = config_xml.parse_file(sys.argv[1])

    for mrc_config in setup.mrc_configs:
        print "%s" % mrc_config
        for device_config in mrc_config.device_configs:
            print "    %s" % device_config
    print

    setup_loader = config.SetupLoader(setup)
    setup_loader.progress_changed.connect(print_progress)
    setup_loader() # Execute the setup loader

    print "SetupLoader results: ", setup_loader.is_complete(), setup_loader.has_failed(), setup_loader.get_result()

    print "Current setup:"
    print application_registry.instance.get('active_setup')

