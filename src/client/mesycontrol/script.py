#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

import contextlib
import functools
import importlib
import logging
import secrets
import signal
import string
import sys

from mesycontrol.qt import QtCore, Property
from mesycontrol import app_context, util, mrc_connection, hardware_controller, hardware_model
from mesycontrol.future import get_future_result

class DeviceWrapper(QtCore.QObject):
    def __init__(self, device, parent=None):
        super(DeviceWrapper, self).__init__(parent)
        self._wrapped = device

    def __getitem__(self, key):
        return self.read_parameter(key)

    def __setitem__(self, key, value):
        return self.set_parameter(key, value)

    def __getattr__(self, attr):
        return getattr(self._wrapped, attr)

    def __str__(self):
        return str(self._wrapped)

    def get_rc(self):
        return self._wrapped.rc

    def set_rc(self, onOff):
        return get_future_result(self._wrapped.set_rc(onOff))

    rc = Property(bool, get_rc, set_rc)

    def read_parameter(self, addr):
        return get_future_result(self._wrapped.read_parameter(addr))

    def set_parameter(self, addr, value):
        return get_future_result(self._wrapped.set_parameter(addr, value))


class MRCWrapper(QtCore.QObject):
    def __init__(self, mrc, parent=None):
        super(MRCWrapper, self).__init__(parent)
        self._wrapped = mrc

    def __getitem__(self, bus):
        if bus not in range(2):
            raise KeyError("No such bus: %d" % bus)

        class bus_proxy(object):
            def __getitem__(proxy_self, dev):
                return DeviceWrapper(self._wrapped.get_device(bus, dev))

            def __str__(proxy_self):
                parts = list()
                for device in self._wrapped.get_devices(bus=bus):
                    parts.append("%d: %s" % (device.address, device))

                return "Bus %i: {%s}" % (bus, ", ".join(parts))

        return bus_proxy()

    def __getattr__(self, attr):
        return getattr(self._wrapped, attr)

    def __str__(self):
        return str(self._wrapped)

    def connectMrc(self):
        return get_future_result(self._wrapped.connectMrc())

    def scanbus(self, bus):
        # Response is a protobuf ScanbusResult. Each object in the 'entries'
        # member is a ScanbusEntry object.
        response = get_future_result(self._wrapped.scanbus(bus)).response
        return response.scanbus_result.entries

    def get_devices(self, bus=None):
        devices = self._wrapped.get_devices(bus)
        return [DeviceWrapper(dev) for dev in devices]

class ScriptContext(object):
    def __init__(self, appContext):
        self.appContext: app_context.Context = appContext
        self.quit = False

    def make_mrc(self, url):
        connection = mrc_connection.factory(url=url)
        controller = hardware_controller.Controller(connection)
        mrc = hardware_model.HardwareMrc(url)
        mrc.set_controller(controller)
        self.appContext.app_registry.hw.add_mrc(mrc)
        return MRCWrapper(mrc)

    def get_device_profile(self, device_idc):
        return self.appContext.device_registry.get_device_profile(device_idc)

    def get_all_mrcs(self):
        return [mrc for mrc in self.appContext.app_registry.get_mrcs()]

    def shutdown(self):
        self.appContext.shutdown()

@contextlib.contextmanager
def get_script_context(log_level=logging.INFO):
    try:
        # Setup logging. Has no effect if logging has already been setup.
        logging.basicConfig(level=log_level,
                format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')
        if logging.getLogger().level == logging.NOTSET:
            logging.getLogger().handlers[0].setLevel(log_level)

        # If a QCoreApplication or QApplication instance exists assume
        # everything is setup and ready. Otherwise install the custom garbage
        # collector and setup signal handling.
        qapp = QtCore.QCoreApplication.instance()

        if qapp is None:
            qapp = QtCore.QCoreApplication(sys.argv)
            gc   = util.GarbageCollector()

            ## Signal handling
            #def signal_handler(signum, frame):
            #    logging.info("Received signal %s. Quitting...",
            #            signal.signum_to_name.get(signum, "%d" % signum))
            #    qapp.quit()

            #signal.signum_to_name = dict((getattr(signal, n), n)
            #        for n in dir(signal) if n.startswith('SIG') and '_' not in n)
            #signal.signal(signal.SIGINT, signal_handler)

        appContext = app_context.Context(
                sys.executable if getattr(sys, 'frozen', False) else __file__)
        scriptContext = ScriptContext(appContext)
        yield scriptContext
    finally:
        if scriptContext is not None:
            scriptContext.shutdown()
        try:
            del gc
        except NameError:
            pass

# Source for gensym() and load_module(): https://medium.com/@david.bonn.2010/dynamic-loading-of-python-code-2617c04e5f3f
def gensym(length=32, prefix="gensym_"):
    """
    generates a fairly unique symbol, used to make a module name,
    used as a helper function for load_module

    :return: generated symbol
    """
    alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits
    symbol = "".join([secrets.choice(alphabet) for i in range(length)])

    return prefix + symbol


def load_module(source, module_name=None):
    """
    reads file source and loads it as a module

    :param source: file to load
    :param module_name: name of module to register in sys.modules
    :return: loaded module
    """

    if module_name is None:
        module_name = gensym()

    spec = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module

def script_runner_main():
    if len(sys.argv) < 3:
        print(f"""Usage: <mrc-url> <script-py> [--debug] [script-args]

Generic runner for mesycontrol scripts. The script-py file must contain a main()
function taking a context object and an optional list of arguments:

  def main(ctx: mesycontrol.script.ScriptContext, mrc: script.MRCWrapper, args: List[str]):
        mrcs = ctx.get_all_mrcs()
        # Interact with the MRCs here.

Accepted mrc-url schemes:
  - For serial connections:
      <serial_port>@<baud> | serial://<serial_port>[@<baud>]
      e.g. /dev/ttyUSB0, /dev/ttyUSB0@115200
  - For TCP connections (serial server connected to an MRC1):
      <host>:<port>
      tcp://<host>[:<port=4001>]
  - For connections to a mesycontrol server:
      mc://<host>[:<port=23000>]
"""
    )
        sys.exit(0)


    mrcUrl = sys.argv[1]
    scriptFile = sys.argv[2]
    scriptArgs = sys.argv[3:]
    doDebug = "--debug" in sys.argv

    print(f"{mrcUrl=}, {scriptFile=}, {scriptArgs=}")

    try:
        scriptModule = load_module(scriptFile)
        scriptMain = scriptModule.main
    except Exception as e:
        print(f"Failed to load script file {scriptFile}: {e}")
        sys.exit(1)

    with get_script_context(logging.DEBUG if doDebug else logging.INFO) as ctx:
        def signal_handler(ctx, signum, frame):
            ctx.quit = True

        signal.signal(signal.SIGINT, functools.partial(signal_handler, ctx))

        mrc = ctx.make_mrc(mrcUrl)
        connectResult = mrc.connectMrc()
        if not connectResult:
            print(f"Failed to connect to mrc {mrcUrl}, {connectResult=}")
            sys.exit(1)

        print(f"Connected to mrc {mrcUrl=}, executing 'main' from {scriptFile}")
        scriptMain(ctx, mrc, scriptArgs)

def script_runner_run(scriptMain):
    if len(sys.argv) != 2:
        print(f"""Usage: {sys.argv[0]} <mrc-url>

    Accepted mrc-url schemes:
        - For serial connections:
            <serial_port>@<baud> | serial://<serial_port>[@<baud>]
            e.g. /dev/ttyUSB0, /dev/ttyUSB0@115200
        - For TCP connections (serial server connected to an MRC1):
            <host>:<port>
            tcp://<host>[:<port=4001>]
        - For connections to a mesycontrol server:
            mc://<host>[:<port=23000>]
    """)
        sys.exit(1)

    with get_script_context() as ctx:
        mrc = ctx.make_mrc(sys.argv[1])
        mrc.connectMrc()
        scriptMain(ctx, mrc, sys.argv[2:])

if __name__ == "__main__":
    script_runner_main()
