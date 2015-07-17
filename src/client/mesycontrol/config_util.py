#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtSlot
from qt import Qt
from qt import QtCore

import future
import hardware_controller
import itertools
import logging
import model_util
import util
import sys

log = logging.getLogger(__name__)

class GeneratorRunner(QtCore.QObject):
    def __init__(self, generator=None, parent=None):
        super(GeneratorRunner, self).__init__(parent)

        self.generator = generator
        self.log = util.make_logging_source_adapter(__name__, self)

    # Note about using QMetaObject.invokeMethod() in start() and
    # _future_yielded():
    #
    # If the generator yields a Future object that completes immediately a
    # callback added via add_done_callback() will also be executed immediately.
    # As the on_done() callback in _future_yielded() calls _next() again the
    # call stack grows. This can quickly lead to the call stack exceeding its
    # maximum size.
    #
    # To avoid this the call to _next() is queued in the Qt event loop and the
    # current invocation of _next() can return.

    def start(self):
        """Start execution of the generator.
        Requires a running Qt event loop (or calls to processEvents()).
        Returns a Future that fullfills on generator termination.
        """

        self._start()

        if self.generator is None:
            raise RuntimeError("No generator function set")

        self.arg    = None
        self.result = future.Future()

        QtCore.QMetaObject.invokeMethod(self, "_next", Qt.QueuedConnection)

        return self.result

    def close(self):
        if self.generator is None:
            raise RuntimeError("No generator function set")

        self.generator.close()

    @pyqtSlot()
    def _next(self):
        while True:
            try:
                obj = self.generator.send(self.arg)

                self.log.info("Generator %s yielded %s (%s)", self.generator, obj, type(obj))

                if isinstance(obj, future.Future):
                    self.log.debug("Future yielded")
                    if self._future_yielded(obj):
                        return

                elif isinstance(obj, ProgressUpdate):
                    self.log.debug("ProgressUpdate yielded")
                    self._progress_update(obj)

                else:
                    self.log.debug("Calling _object_yielded with %s", obj)
                    self.arg, do_return = self._object_yielded(obj)

                    self.log.debug("invoked _object_yielded: %s, %s", self.arg, do_return)

                    if do_return:
                        self.log.debug("return flag is set; returning from _next")
                        return

                    if self.arg == ACTION_ABORT:
                        self.log.debug("arg is ACTION_ABORT. closing generator")
                        self.log.info("Abort: closing generator")
                        self.generator.close()
                        self.log.info("Abort: setting result to False")
                        self.result.set_result(False)
                        return

            except StopIteration:
                self._stop_iteration()
                return

            except Exception as e:
                try:
                    self._exception(e)
                except Exception as e:
                    self.result.set_exception(e)
                    self.generator.close()
                    self.log.exception("Generator")
                    return

    def _start(self):
        """Called right before starting the generator. Use for initialization
        if needed."""
        pass

    def _future_yielded(self, f):
        """Handles the case where the generator yields a Future object.
        The default action is to wait for the future to complete and then send
        the future back into the generator.
        """
        def on_done(f):
            self.arg = f
            QtCore.QMetaObject.invokeMethod(self, "_next", Qt.QueuedConnection)

        f.add_done_callback(on_done)
        return True

    def _progress_update(self, progress):
        """Handles the case where the generator yields a ProgressUpdate. The
        default is to update the results progress.
        """
        self.result.set_progress_range(0, progress.total)
        self.result.set_progress(progress.current)
        self.result.set_progress_text(progress.text)

    def _object_yielded(self, obj):
        """Called if the generator yields any object other than Future or
        ProgressUpdate."""
        raise NotImplementedError()

    def _stop_iteration(self):
        """Called on encountering a StopIteration exception. The default is to
        set the results value to True."""

        if not self.result.done():
            self.result.set_result(True)

    def _exception(self, e):
        """Called on encountering an exception other than StopIteration. The
        default action is to reraise the exception with the original
        traceback."""

        raise e, None, sys.exc_info()[2]

class ProgressUpdate(object):
    def __init__(self, current, total, text=str()):
        self.current = current
        self.total   = total
        self.text    = text

    def __iadd__(self, other):
        self.current += other
        return self

    def increment(self, delta=1):
        self += delta
        return self

    def __str__(self):
        if not len(self.text):
            return "%d/%d" % (self.current, self.total)
        return "%d/%d: %s" % (self.current, self.total, self.text)

class SetParameterError(RuntimeError):
    def __init__(self, set_result):
        self.set_result = set_result
        self.url = None

    def __str__(self):
        if self.url is not None:
            return "SetParameterError(url=%s, %s)" % (
                    self.url, self.set_result)
        return "SetParameterError(%s)" % str(self.set_result)

class IDCConflict(RuntimeError):
    pass

class MissingDestinationDevice(RuntimeError):
    def __init__(self, url, bus, dev):
        self.url = url
        self.bus = bus
        self.dev = dev

class MissingDestinationMRC(RuntimeError):
    def __init__(self, url):
        self.url = url

class Aborted(RuntimeError):
    pass

ACTION_SKIP, ACTION_ABORT, ACTION_RETRY = range(3)

def apply_device_config(device):
    """Device may be an app_model.Device instance or a DeviceBase
    subclass."""

    if device.idc_conflict:
        raise IDCConflict("%s" % device)

    criticals       = (yield device.get_critical_config_parameters()).result()
    non_criticals   = (yield device.get_non_critical_config_parameters()).result()

    gen = apply_parameters(device.cfg, device.hw, criticals, non_criticals)
    arg = None

    while True:
        try:
            obj = gen.send(arg)

            if isinstance(obj, SetParameterError):
                obj.url = device.mrc.url

            arg = yield obj
        except StopIteration:
            non_criticals = obj
            break
        except GeneratorExit:
            gen.close()
            return

def apply_parameters(source, dest, criticals, non_criticals):
    """Write parameters from source to dest. First criticals are set to their
    safe value, then non_criticals are written to the destination and finally
    criticals are set to the value they have in the source device.
    """
    def check_idcs():
        if source.idc != dest.idc:
            raise IDCConflict(
                    "IDCConflict: mrc=%s, bus=%d, dev=%d, src-idc=%d, dest-idc=%d" %
                    (source.mrc.get_display_url(), source.bus, source.address,
                        source.idc, dest.idc))

    check_idcs()
    values = dict()

    # Get available parameters directly from the sources cache. This is
    # mostly to smoothen progress updates as otherwise, if all parameters
    # are in the sources cache, progress would jump to around 50%
    # instantly.
    
    for pp in itertools.chain(non_criticals, criticals):
        if source.has_cached_parameter(pp.address):
            values[pp.address] = source.get_cached_parameter(pp.address)

    # number of parameters left to read from source
    total_progress  = (len(non_criticals) + len(criticals)) - len(values)
    # number of parameters to be written to dest
    total_progress += len(non_criticals) + 2 * len(criticals)

    progress      = ProgressUpdate(current=0, total=total_progress)
    progress.text = ("Reading from source (%s,%d,%d)" %
            (source.mrc.get_display_url(), source.bus, source.address))

    yield progress

    # Note: The code below executes async operations (get and set
    # parameter) in bursts instead of queueing one request and waiting for
    # its future to complete. This way the devices request queue won't be
    # empty and thus polling won't interfere with our requests.

    futures = list()

    # Read remaining parameters from source.
    for pp in filter(lambda pp: pp.address not in values,
            itertools.chain(non_criticals, criticals)):

        futures.append(source.get_parameter(pp.address))

    for f in futures:
        yield f
        check_idcs()
        r = f.result()

        values[r.address] = r.value

        yield progress.increment()

    if len(criticals):
        progress.text = "Setting critical parameters to safe values"

    futures = list()

    # Set safe values for critical parameters.
    for pp in criticals:
        futures.append(dest.set_parameter(pp.address, pp.safe_value))

    gen = run_set_parameter_futures(futures)
    arg = None

    while True:
        try:
            check_idcs()
            obj = gen.send(arg)
            arg = yield obj

            if isinstance(obj, future.Future):
                yield progress.increment()
        except StopIteration:
            break
        except GeneratorExit:
            gen.close()
            return

    progress.text = ("Writing to destination (%s,%d,%d)" %
            (dest.mrc.get_display_url(), dest.bus, dest.address))

    futures = list()

    # Set non-criticals
    for pp in non_criticals:
        value = values[pp.address]
        futures.append(dest.set_parameter(pp.address, value))

    gen = run_set_parameter_futures(futures)
    arg = None

    while True:
        try:
            check_idcs()
            obj = gen.send(arg)
            arg = yield obj

            if isinstance(obj, future.Future):
                yield progress.increment()
        except StopIteration:
            break
        except GeneratorExit:
            gen.close()
            return

    if len(criticals):
        progress.text = ("Writing critical parameters to destination (%s,%d,%d)" %
            (dest.mrc.get_display_url(), dest.bus, dest.address))

    futures = list()

    # Finally set criticals to their config values
    for pp in criticals:
        value = values[pp.address]
        futures.append(dest.set_parameter(pp.address, value))

    gen = run_set_parameter_futures(futures)
    arg = None

    while True:
        try:
            check_idcs()
            obj = gen.send(arg)
            arg = yield obj

            if isinstance(obj, future.Future):
                yield progress.increment()
        except StopIteration:
            break
        except GeneratorExit:
            gen.close()
            return

    progress.text = "Parameters applied successfully"
    yield progress

    raise StopIteration()

def run_set_parameter_futures(futures):
    log.debug("run_set_parameter_futures: %s", futures)
    for f in futures:
        try:
            f = yield f
            r = f.result()
            if not r:
                raise SetParameterError(r)
            log.debug("run_set_parameter_futures: %s done", f)
        except GeneratorExit:
            for f in filter(lambda f: not f.done(), futures):
                f.cancel()
            return
        except Exception as e:
            log.debug("run_set_parameter_futures: yielding %s", e)
            action = yield e

            if action == ACTION_SKIP:
                log.debug("run_set_parameter_futures: skipping one future")
                continue

            raise RuntimeError("unhandled action: %s" % action)

def establish_connections(setup, hardware_registry):
    progress = ProgressUpdate(current=0, total=len(setup))

    for cfg_mrc in setup:
        progress.text = "Connecting to %s" % cfg_mrc.get_display_url()
        yield progress

        hw_mrc = hardware_registry.get_mrc(cfg_mrc.url)

        if hw_mrc is None:
            model_util.add_mrc_connection(hardware_registry=hardware_registry,
                    url=cfg_mrc.url, do_connect=False)

            hw_mrc = hardware_registry.get_mrc(cfg_mrc.url)

        if hw_mrc.is_connecting():
            # Cancel active connection attempts as we need the Future returned
            # by connect().
            yield hw_mrc.disconnect()

        if hw_mrc.is_disconnected():
            action = ACTION_RETRY

            while action == ACTION_RETRY:
                f = yield hw_mrc.connect()

                try:
                    f.result()
                    break
                except hardware_controller.TimeoutError as e:
                    action = yield e

                    if action == ACTION_SKIP:
                        break

            if action == ACTION_SKIP:
                continue

        if hw_mrc.is_connected():
            progress.text = "Connected to %s" % cfg_mrc.get_display_url()
            yield progress
            yield hw_mrc.scanbus(0)
            yield hw_mrc.scanbus(1)

        progress.increment()

def connect_and_apply_setup(app_registry, device_registry):
    setup = app_registry.cfg
    # MRCs to connect + device configs to apply
    total_progress = len(setup) + sum(len(mrc) for mrc in setup)
    progress       = ProgressUpdate(current=0, total=total_progress)
    progress.text  = "Establishing MRC connections"

    yield progress

    gen = establish_connections(setup, app_registry.hw)
    arg = None

    while True:
        try:
            obj = gen.send(arg)

            if isinstance(obj, ProgressUpdate):
                progress.text = obj.text
                yield progress.increment()
                arg = None
            else:
                arg = yield obj

        except StopIteration:
            # From inside the generator
            break
        except GeneratorExit:
            # From the caller invoking close()
            gen.close()
            return

    gen = apply_setup(app_registry, device_registry)
    arg = None

    while True:
        try:
            obj = gen.send(arg)

            if isinstance(obj, ProgressUpdate):
                progress.current = len(setup) + obj.current

                if hasattr(obj, 'subprogress'):
                    progress.subprogress = obj.subprogress

                yield progress
                arg = None
            else:
                arg = yield obj

        except StopIteration:
            break
        except GeneratorExit:
            gen.close()
            return

def apply_setup(app_registry, device_registry):
    source   = app_registry.cfg
    progress = ProgressUpdate(current=0, total=sum(len(mrc) for mrc in source))
    progress.subprogress = ProgressUpdate(current=0, total=0)

    def _apply_device_config(device):
        action = ACTION_RETRY

        while device.hw is None and action == ACTION_RETRY:
            action = yield MissingDestinationDevice(
                    url=device.mrc.url, bus=device.bus, dev=device.address)

            if action == ACTION_SKIP:
                raise StopIteration()

        gen = apply_device_config(device)
        arg = None

        while True:
            try:
                obj = gen.send(arg)

                if isinstance(obj, ProgressUpdate):
                    progress.subprogress = obj
                    yield progress
                    arg = None
                else:
                    arg = yield obj

            except StopIteration:
                break
            except GeneratorExit:
                gen.close()
                return

    def _apply_mrc_config(app_mrc):
        action   = ACTION_RETRY

        while app_mrc.hw is None and action == ACTION_RETRY:
            action = yield MissingDestinationMRC(url=app_mrc.url)

            if action == ACTION_SKIP:
                raise StopIteration()

        if not app_mrc.hw.is_connected():
            return

        for device in (d for d in app_mrc if d.cfg is not None):
            action = ACTION_RETRY

            while action == ACTION_RETRY:

                gen = _apply_device_config(device)
                arg = None

                while True:
                    try:
                        obj = gen.send(arg)
                        arg = yield obj
                    except StopIteration:
                        action = None
                        break
                    except GeneratorExit:
                        gen.close()
                        return
                    except IDCConflict as e:
                        action = yield e

                        if action in (ACTION_SKIP, ACTION_RETRY):
                            break

            yield progress.increment()

    for mrc in (m for m in app_registry if m.cfg is not None):
        gen = _apply_mrc_config(mrc)
        arg = None

        while True:
            try:
                obj = gen.send(arg)
                arg = yield obj
            except StopIteration:
                break
            except GeneratorExit:
                gen.close()
                return