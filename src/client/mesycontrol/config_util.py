#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtSlot
from qt import Qt
from qt import QtCore

from functools import partial

from basic_model import IDCConflict
import basic_model as bm
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
        self._current = int(current)
        self._total   = int(total)
        self.text    = text

        self._check()

    def __iadd__(self, other):
        self._current += other
        self._check()
        return self

    def increment(self, delta=1):
        self += delta
        return self

    def __str__(self):
        if not len(self.text):
            ret = "ProgressUpdate(%d/%d" % (self.current, self.total)
        else:
            ret = "ProgressUpdate(%d/%d: %s" % (self.current, self.total, self.text)

        if hasattr(self, 'subprogress'):
            sp = self.subprogress
            if not len(sp.text):
                sub = "%d/%d" % (sp.current, sp.total)
            else:
                sub = "%d/%d: %s" % (sp.current, sp.total, sp.text)
            ret += ", subprogress: " + sub
        ret += ')'
        return ret

    def _check(self):
        assert self.current <= self.total

    def get_current(self):
        return self._current

    def get_total(self):
        return self._total

    def set_current(self, cur):
        self._current = cur
        self._check()

    def set_total(self, total):
        self._total = total
        self._check()

    current = property(get_current, set_current)
    total   = property(get_total, set_total)

class SetParameterError(RuntimeError):
    def __init__(self, set_result, device=None):
        self.set_result = set_result
        self.url = None
        self.device = device

    def __str__(self):
        if self.url is not None:
            return "SetParameterError(url=%s, %s)" % (
                    self.url, self.set_result)
        return "SetParameterError(%s)" % str(self.set_result)

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

    gen = apply_parameters(source=device.cfg, dest=device.hw,
            criticals=criticals, non_criticals=non_criticals)
    arg = None

    try:
        polling = device.hw.mrc.polling
        device.hw.mrc.polling = False

        while True:
            try:
                obj = gen.send(arg)

                if isinstance(obj, SetParameterError):
                    obj.url = device.mrc.url
                    obj.device = device

                arg = yield obj
            except StopIteration:
                break
            except GeneratorExit:
                gen.close()
                return

        # extensions
        for name, value in device.cfg.get_extensions().iteritems():
            device.hw.set_extension(name, value)
    finally:
        device.hw.mrc.polling = polling

def run_callables_generator(callables):
    progress = ProgressUpdate(current=0, total=len(callables))

    for c in callables:
        action = ACTION_RETRY

        while action == ACTION_RETRY:
            try:
                f = yield c()
                r = f.result()
                if isinstance(r, bm.SetResult) and not r:
                    raise SetParameterError(r)
                yield progress.increment()
                break
            except GeneratorExit:
                return
            except Exception as e:
                action = yield e
                if action == ACTION_SKIP:
                    break

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


def apply_device_configs(devices):
    """Applies config values to the hardware for each of the given devices.
    Required MRC connections are established.
    """
    skipped_mrcs    = set()
    mrcs_to_connect = set(d.mrc for d in devices if (not d.mrc.has_hw or not d.mrc.hw.is_connected()))

    progress             = ProgressUpdate(current=0, total=len(mrcs_to_connect) + len(devices))
    progress.subprogress = ProgressUpdate(current=0, total=0)

    yield progress

    for device in devices:
        mrc = device.mrc

        if mrc.hw is None:
            model_util.add_mrc_connection(
                    hardware_registry=mrc.mrc_registry.hw,
                    url=mrc.url, do_connect=False)

        if mrc in skipped_mrcs:
            continue

        if mrc.hw.is_connecting():
            # Cancel active connection attempts as we need the Future returned
            # by connect().
            yield mrc.hw.disconnect()

        if mrc.hw.is_disconnected():
            progress.text = "Connecting to %s" % mrc.get_display_url()
            yield progress

            action = ACTION_RETRY

            while action == ACTION_RETRY:
                f = yield mrc.hw.connect()

                try:
                    f.result()
                    break
                except hardware_controller.TimeoutError as e:
                    action = yield e

                    if action == ACTION_SKIP:
                        skipped_mrcs.add(mrc)
                        break

            if action == ACTION_SKIP:
                yield progress.increment()
                continue

        try:
            polling = mrc.hw.polling
            mrc.hw.polling = False

            (yield mrc.hw.scanbus(0)).result()
            (yield mrc.hw.scanbus(1)).result()
            progress.text = "Connected to %s" % mrc.get_display_url()

            action = ACTION_RETRY

            while device.hw is None and action == ACTION_RETRY:
                action = yield MissingDestinationDevice(
                        url=device.mrc.url, bus=device.bus, dev=device.address)

                if action == ACTION_SKIP:
                    break

            if action == ACTION_SKIP:
                yield progress.increment()
                continue

            progress.text = "Current device: (%s, %d, %d)" % (
                    device.mrc.get_display_url(), device.bus, device.address)
            yield progress

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

            yield progress.increment()
        finally:
            mrc.hw.polling = polling

def fill_device_configs(devices):
    """For each of the given devices read config parameters from the hardware
    and use them to fill the device config.
    Device extensions will also be copied from hardware to config.
    """
    skipped_mrcs    = set()
    mrcs_to_connect = set(d.mrc for d in devices if (not d.mrc.has_hw or not d.mrc.hw.is_connected()))

    progress = ProgressUpdate(current=0, total=len(mrcs_to_connect) + len(devices))
    progress.subprogress = ProgressUpdate(current=0, total=0)

    for device in devices:
        mrc = device.mrc

        if mrc.hw is None:
            model_util.add_mrc_connection(
                    hardware_registry=mrc.mrc_registry.hw,
                    url=mrc.url, do_connect=False)

        if mrc in skipped_mrcs:
            continue

        if mrc.hw.is_connecting():
            # Cancel active connection attempts as we need the Future returned
            # by connect().
            yield mrc.hw.disconnect()

        if mrc.hw.is_disconnected():
            progress.text = "Connecting to %s" % mrc.get_display_url()
            yield progress

            action = ACTION_RETRY

            while action == ACTION_RETRY:
                f = yield mrc.hw.connect()

                try:
                    f.result()
                    yield progress.increment()
                    break
                except hardware_controller.TimeoutError as e:
                    action = yield e

                    if action == ACTION_SKIP:
                        skipped_mrcs.add(mrc)
                        break

            if action == ACTION_SKIP:
                continue

        try:
            polling = mrc.hw.polling
            mrc.hw.polling = False

            (yield mrc.hw.scanbus(0)).result()
            (yield mrc.hw.scanbus(1)).result()

            if not device.has_cfg:
                device.create_config()

            progress.text = "Current device: (%s, %d, %d)" % (
                    device.mrc.get_display_url(), device.bus, device.address)
            yield progress

            parameters = (yield device.get_config_parameters()).result()

            gen = apply_parameters(source=device.hw, dest=device.cfg,
                    criticals=list(), non_criticals=parameters)
            arg = None

            while True:
                try:
                    obj = gen.send(arg)

                    if isinstance(obj, SetParameterError):
                        obj.url = device.mrc.url
                        obj.device = device
                        arg = yield obj

                    elif isinstance(obj, ProgressUpdate):
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

            # extensions
            for name, value in device.hw.get_extensions().iteritems():
                device.cfg.set_extension(name, value)

            yield progress.increment()
        finally:
            mrc.hw.polling = polling

def read_config_parameters(devices):
    progress = ProgressUpdate(current=0, total=len(devices))
    progress.subprogress = ProgressUpdate(current=0, total=0)
    yield progress

    for device in devices:
        try:
            hw_mrc = device.mrc.hw
            polling = hw_mrc.polling
            hw_mrc.polling = False

            params = (yield device.get_config_parameters()).result()
            log.debug("read_config_parameters: params=%s", [p.address for p in params])
            progress.subprogress.current = 0
            progress.subprogress.total   = len(params)
            progress.text  = "Reading from (%s, %d, %X)" % (
                    device.mrc.get_display_url(), device.bus, device.address)
            yield progress

            for param in params:
                log.debug("read_config_parameters: reading %d", param.address)
                yield device.hw.read_parameter(param.address)
                progress.subprogress.text = "Reading parameter %s (address=%d)" % (
                        param.name, param.address)
                progress.subprogress.increment()
                yield progress

            device.update_config_applied()

            yield progress.increment()
        finally:
            hw_mrc.polling = polling

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

    # Read remaining parameters from source.
    addresses = (pp.address for pp in filter(lambda pp: pp.address not in values,
        itertools.chain(non_criticals, criticals)))

    gen = run_callables_generator([partial(source.get_parameter, addr)
        for addr in addresses])
    arg = None

    while True:
        try:
            obj = gen.send(arg)

            if isinstance(obj, ProgressUpdate):
                yield progress.increment()
                arg = None
            else:
                arg = yield obj

            if isinstance(obj, future.Future) and not obj.exception():
                r = obj.result()
                values[r.address] = r.value
        except StopIteration:
            break
        except GeneratorExit:
            gen.close()
            return

    # Set safe values for critical parameters.
    if len(criticals):
        progress.text = "Setting critical parameters to safe values"

    addr_values = ((pp.address, pp.safe_value) for pp in criticals)
    gen = run_callables_generator([partial(dest.set_parameter, t[0], t[1])
            for t in addr_values])
    arg = None

    while True:
        try:
            obj = gen.send(arg)
            if isinstance(obj, ProgressUpdate):
                yield progress.increment()
                arg = None
            else:
                arg = yield obj
        except StopIteration:
            break
        except GeneratorExit:
            gen.close()
            return

    # Set non-criticals
    progress.text = ("Writing to destination (%s,%d,%d)" %
            (dest.mrc.get_display_url(), dest.bus, dest.address))

    addr_values = ((pp.address, values[pp.address]) for pp in non_criticals)
    gen = run_callables_generator([partial(dest.set_parameter, t[0], t[1])
            for t in addr_values])
    arg = None

    while True:
        try:
            obj = gen.send(arg)
            if isinstance(obj, ProgressUpdate):
                yield progress.increment()
                arg = None
            else:
                arg = yield obj
        except StopIteration:
            break
        except GeneratorExit:
            gen.close()
            return

    # Finally set criticals to their config values
    if len(criticals):
        progress.text = ("Writing critical parameters to destination (%s,%d,%d)" %
            (dest.mrc.get_display_url(), dest.bus, dest.address))

    addr_values = ((pp.address, values[pp.address]) for pp in criticals)
    gen = run_callables_generator([partial(dest.set_parameter, t[0], t[1])
            for t in addr_values])
    arg = None

    while True:
        try:
            obj = gen.send(arg)
            if isinstance(obj, ProgressUpdate):
                yield progress.increment()
                arg = None
            else:
                arg = yield obj
        except StopIteration:
            break
        except GeneratorExit:
            gen.close()
            return

    progress.text = "Parameters applied successfully"
    yield progress

    raise StopIteration()
