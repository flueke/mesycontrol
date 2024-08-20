#!/usr/bin/env python

# This script shows how to automatically poll all "volatile" (meaning possibly
# fast changing parameters) from all devices connected to the target MRC and
# write the obtained values and additional meta data to an influxdb bucket.

# Change the values of the 'mesyflux_*' variables according to your influxdb
# setup. By default the script tries to obtain the influxdb API access token and
# other settings from the environment variables INFLUXDB_TOKEN, INFLUXDB_ORG,
# INFLUXDB_URL and INFLUXDB_BUCKET. INFLUXDB_TOKEN is required, the other values
# have defaults.

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client import InfluxDBClient, Point, WritePrecision

import os
import signal
import sys
import time

from mesycontrol.script import script_runner_run

# InfluxDB settings
mesyflux_token  = os.environ.get("INFLUXDB_TOKEN")
mesyflux_org    = os.environ.get("INFLUXDB_ORG", default="mesytec")
mesyflux_url    = os.environ.get("INFLUXDB_URL", default="http://localhost:8086")
mesyflux_bucket = os.environ.get("INFLUXDB_BUCKET", default="mesycontrol")

def poll_volatile_parameters(ctx, mrc):
    ret = dict()

    for device in mrc.get_devices():
        # device is a script.DeviceWrapper instance
        # profile is a device_profile.DeviceProfile instance
        profile = ctx.get_device_profile(device.idc)
        print("bus={}, addr=0x{:x}, found device with idc={}, rc={}, type={}".format(
            device.bus, device.address, device.idc, "on " if device.rc else "off", profile.name), end='')

        if device.address_conflict:
            print(", address conflict detected!")
            continue

        volatiles = list(profile.get_volatile_addresses())
        print(": polling {} volatile parameters".format(len(volatiles)))

        paramTuples = list()
        for addr in volatiles:
            readResult = device.read_parameter(addr)
            paramProfile = profile[readResult.address]
            paramTuples.append((readResult, paramProfile))

        ret[device] = paramTuples

    return ret

def write_poll_results_to_influxdb(ctx, mesyfluxWriteApi: influxdb_client.WriteApi, pollResults):
    for device, paramTuples in pollResults.items():
        deviceProfile = ctx.get_device_profile(device.idc)
        p = influxdb_client.Point("mesyflux_auto_poll")

        # These tags are used to uniquely identify each device by mrc-url, bus,
        # bus address and device type.
        p.tag("mrc_url", device.mrc.url)
        p.tag("mrc_bus", device.bus)
        p.tag("mrc_bus_addr", device.address)
        p.tag("device_idc", device.idc)
        p.tag("device_type", deviceProfile.name)

        # Add parameter values and other attribues to the Point instance.
        for readResult, paramProfile in paramTuples:
            paramUnit = paramProfile.units[-1] # device_profile.Unit

            # The raw parameter value as read from the device.
            p.field(paramProfile.name + "_raw", readResult.value)

            # Optional: the parameters register address value
            #p.field(paramProfile.name + "_address", readResult.address)

            # Optional: parameter unit value obtained from the parameters Unit definition
            p.field(paramProfile.name + "_unit_value", paramUnit.unit_value(readResult.value))

            # Label of the parameters unit value, e.g. 'V', 'mA', etc.
            p.field(paramProfile.name + "_unit", paramUnit.label)

        mesyfluxWriteApi.write(bucket=mesyflux_bucket, org=mesyflux_org, record=p)

g_quit = False

def signal_handler(signum, frame):
    global g_quit
    g_quit = True

def main(ctx, mrc, args):

    mesyfluxClient = influxdb_client.InfluxDBClient(url=mesyflux_url, token=mesyflux_token, org=mesyflux_org)
    mesyfluxWriteApi = mesyfluxClient.write_api(write_options=SYNCHRONOUS)

    with mesyfluxClient, mesyfluxWriteApi:
        ScanbusInterval = 5.0 # in seconds
        PollInterval = 1.0 # in seconds

        tScanbus = 0.0
        tPoll = 0.0

        print("Entering polling loop, press Ctrl-C to quit")

        while not g_quit:
            if not mrc.is_connected():
                mrc.connectMrc()
                if mrc.is_connected():
                    print("Connected to mrc {}".format(mrc))
            else:
                if time.monotonic() - tScanbus >= ScanbusInterval:
                    print("scanbus")
                    for bus in range(2):
                        mrc.scanbus(bus)
                    tScanbus = time.monotonic()

                if time.monotonic() - tPoll >= PollInterval:
                    print("poll")
                    pollResults = poll_volatile_parameters(ctx, mrc)
                    write_poll_results_to_influxdb(ctx, mesyfluxWriteApi, pollResults)
                    tPoll = time.monotonic()
                else:
                    time.sleep(0.1)

if __name__ == "__main__":
    script_runner_run(main)
