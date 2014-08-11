#!/usr/bin/env python
# -*- coding: utf-8 -*-

from mesycontrol.script import *
from mesycontrol import config_xml
from mesycontrol import config_loader

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print "Usage: %s <connection-url> <bus> <address> <config_filename>" % sys.argv[0]
        print "Example: %s /dev/ttyUSB0@0 0 1 mhv4_config.xml" % sys.argv[0]
        sys.exit(1)

    url     = sys.argv[1]
    bus     = int(sys.argv[2])
    address = int(sys.argv[3])
    config_filename = sys.argv[4]

    with get_script_context() as ctx:
        config = config_xml.parse_file(config_filename)
        mrc    = ctx.make_connection(url=url)
        mrc.connect()

        for i in range(2):
            print mrc[i]

        device = mrc[bus][address]

        try:
            device_config = config.get_device_configs_by_idc(device.idc)[0]
        except IndexError:
            raise RuntimeError("No device config for idc=%d found in %s" %
                    (device.idc, config_filename))

        loader = config_loader.ConfigLoader(device, device_config)
        loader()

    sys.exit(0)
