#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

# Invocation:
# simple-shell <mrc-url>

# Commands:
# SC, ON, OFF, RST, CP, SE, RE, RB, SM, RM

from __future__ import print_function
import cmd
import logging
import os
import shlex
import signal
import sys

from mesycontrol import app_context
from mesycontrol import mrc_command
from mesycontrol import qt
from mesycontrol import script

class SimpleShell(cmd.Cmd):
    def __init__(self, mrc, stdin=sys.stdin, stdout=sys.stdout):
        cmd.Cmd.__init__(self, stdin=stdin, stdout=stdout)
        self.prompt = 'mesyctrl> '
        self.mrc    = mrc

        if stdin != sys.stdin:
            self.use_rawinput = False

    # Default if no do_*() method matches the cmd prefix
    def default(self, line):
        if line == 'EOF':
            return True # exit on EOF
        return cmd.Cmd.default(self, line)

    # Ignore empty lines
    def emptyline(self):
        return False

    def print(self, *args, **kwargs):
        print(file=self.stdout, *args, **kwargs)

    # ===== Commands =====
    def do_sc(self, line):
        bus = int(shlex.split(line)[0])
        mrc_command.Scanbus(self.mrc, bus)()

        self.print("sc", bus)
        for i in range(16):
            if self.mrc.has_device(bus, i):
                device = self.mrc[bus][i]
                self.print("%2d: %s, rc=%d, conflict=%d" % (i, device, device.rc, device.has_address_conflict()))
            else:
                self.print("%2d: -" % i)

    def do_on(self, line):
        return self._do_rc(line, True)

    def do_off(self, line):
        return self._do_rc(line, False)

    def _do_rc(self, line, on_off):
        try:
            args     = shlex.split(line)
            bus, dev = int(args[0]), int(args[1])
        except ValueError:
            self.print("Invalid arguments")
            return False

        try:
            device   = self.mrc.get_device(bus, dev)
            mrc_command.SetRc(device, bool(on_off))()
        except KeyError:
            self.print("No such device (bus=%d, dev=%d)" % (bus, dev))
        else:
            self.print("%s: rc=%s" %  (device, device.rc))

    def do_se(self, line):
        try:
            args = shlex.split(line)
            bus, dev, par, val = [int(v) for v in args[:4]]
        except ValueError:
            self.print("Invalid arguments")
            return False

        try:
            device = self.mrc.get_device(bus, dev)
            result = mrc_command.SetParameter(device, par, val)()
            self.print("se %d %d %d -> %d" % (bus, dev, par, result))
        except KeyError:
            self.print("No such device (bus=%d, dev=%d)" % (bus, dev))

    def do_re(self, line):
        try:
            args = shlex.split(line)
            bus, dev, par = [int(v) for v in args[:3]]
        except ValueError:
            self.print("Invalid arguments")
            return False

        try:
            device = self.mrc.get_device(bus, dev)
            result = mrc_command.ReadParameter(device, par)()
            self.print("re %d %d %d -> %d" % (bus, dev, par, result))
        except KeyError:
            self.print("No such device (bus=%d, dev=%d)" % (bus, dev))

    def do_rb(self, line):
        try:
            args = shlex.split(line)
            bus, dev, par, length = [int(v) for v in args[:4]]
        except ValueError:
            self.print("Invalid arguments")
            return False

        try:
            device = self.mrc.get_device(bus, dev)
            result = mrc_command.ReadMulti(device, par, length)()
            self.print("rb %d %d %d %d -> %s" % (bus, dev, par, length, result))
        except KeyError:
            self.print("No such device (bus=%d, dev=%d)" % (bus, dev))

    def do_quit(self, line):
        return True

def signal_handler(signum, frame):
    logging.info("Received signal %s. Quitting...",
            signal.signum_to_name.get(signum, "%d" % signum))
    qt.QtCore.QCoreApplication.quit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    signal.signum_to_name = dict((getattr(signal, n), n)
            for n in dir(signal) if n.startswith('SIG') and '_' not in n)
    signal.signal(signal.SIGINT, signal_handler)

    app     = qt.QtGui.QApplication(sys.argv)
    context = app_context.Context(sys.executable if getattr(sys, 'frozen', False) else __file__)
    # Update the environments path to easily find the mesycontrol_server binary.
    os.environ['PATH'] = context.bin_dir + os.pathsep + os.environ['PATH']

    try:
        mrc_url = sys.argv[1]
    except IndexError:
        basename = os.path.basename(sys.argv[0])
        print("Usage:   %s <mrc-url>" % basename)
        print("Example: %s /dev/ttyUSB0" % basename)
        sys.exit(1)

    try:
        mrc = script.MRCWrapper(context.make_mrc_connection(url=mrc_url))
        print("Connecting to %s..." % mrc)
        mrc.connect()
        if mrc.is_connected():
            print("Connected to %s" % mrc)
        else:
            raise RuntimeError("Could not connect to %s" % mrc)

        ss = SimpleShell(script.MRCWrapper(mrc))
        ss.cmdloop("mesycontrol simple shell")

    finally:
        print("Bye, bye!")
        context.shutdown()
