#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtSlot
from qt import Qt
from qt import QtCore

import future
import itertools
import util

class SetParameterError(RuntimeError):
    pass

class IDCConflict(RuntimeError):
    pass

class ProgressUpdate(object):
    __slots__ = ['current', 'total', 'text']

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

def apply_device_config(source, dest, device_profile):
    """Apply device config operation in the form of a generator.
    Yields Futures and ProgressUpdates. Raises StopIteration on completion.
    """

    def check_idcs():
        if source.idc != dest.idc:
            raise IDCConflict("idc conflict between source and dest")

        if source.idc != device_profile.idc:
            raise IDCConflict("idc conflict between source and device profile")

    try:
        check_idcs()

        non_criticals   = device_profile.get_non_critical_config_parameters()
        criticals       = device_profile.get_critical_parameters()
        values          = dict()

        # Get available parameters directly from the sources cache. This is
        # mostly to smoothen progress updates as otherwise progress would jump
        # to around 50% instantly if all parameters are in the sources cache.

        for pp in itertools.chain(non_criticals, criticals):
            if source.has_cached_parameter(pp.address):
                values[pp.address] = source.get_cached_parameter(pp.address)

        # number of parameters left to read from source
        total_progress  = (len(non_criticals) + len(criticals)) - len(values)
        # number of parameters to be written to dest
        total_progress += len(non_criticals) + 2 * len(criticals)

        progress      = ProgressUpdate(current=0, total=total_progress)
        progress.text = "Reading from source"

        yield progress

        # Note: The code below executes async operations (get and set
        # parameter) in bursts instead of queueing one request and waiting for
        # its future to complete. This way the devices request queue won't be
        # empty and thus polling won't interfere with our requests.

        futures = list()

        # Read remaining parameters from source.
        for pp in filter(lambda pp: pp.address not in values,
                itertools.chain(non_criticals, criticals)):

            check_idcs()
            futures.append(source.get_parameter(pp.address))

        for f in futures:
            yield f
            r = f.result()

            values[r.address] = r.value

            yield progress.increment()

        if len(criticals):
            progress.text = "Setting critical parameters to safe values"

        futures = list()

        # Set safe values for critical parameters.
        for pp in criticals:
            check_idcs()
            futures.append(dest.set_parameter(pp.address, pp.safe_value))

        for f in futures:
            f = yield f
            r = f.result()

            if not r:
                raise SetParameterError(r)

            yield progress.increment()

        progress.text = "Writing to destination"

        futures = list()

        # Set non-criticals
        for pp in non_criticals:
            check_idcs()
            value = values[pp.address]
            futures.append(dest.set_parameter(pp.address, value))

        for f in futures:
            f = yield f
            r = f.result()

            if not r:
                raise SetParameterError(r)

            yield progress.increment()

        if len(criticals):
            progress.text = "Writing critical parameters to destination"

        futures = list()

        # Finally set criticals to their config values
        for pp in criticals:
            check_idcs()
            value = values[pp.address]
            futures.append(dest.set_parameter(pp.address, value))

        for f in futures:
            f = yield f
            r = f.result()

            if not r:
                raise SetParameterError(r)

            yield progress.increment()

        progress.text = "Config applied successfully"
        yield progress

        raise StopIteration()
    finally:
        pass

class ApplyDeviceConfigRunner(QtCore.QObject):
    def __init__(self, source, dest, device_profile, parent=None):
        super(ApplyDeviceConfigRunner, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.source = source
        self.dest   = dest
        self.device_profile = device_profile

    # Note about using QMetaObject.invokeMethod() in start() and _next():
    # If the apply_device_config generator yields a Future object that
    # completes immediately a callback added via add_done_callback() will also
    # be executed immediately. As the on_done() callback below calls _next()
    # again the call stack grows. This can quickly lead to the call stack
    # exceeding its maximum size.
    # To avoid this the call to _next() is queued in the Qt event loop and the
    # current invocation of _next() can return.
    def start(self):
        self.apply_generator = apply_device_config(self.source, self.dest,
                self.device_profile)
        self.arg = None
        self.result_future = future.Future()
        QtCore.QMetaObject.invokeMethod(self, "_next", Qt.QueuedConnection)
        return self.result_future

    @pyqtSlot()
    def _next(self):
        while True:
            try:
                obj = self.apply_generator.send(self.arg)

                if isinstance(obj, future.Future):

                    def on_done(f):
                        self.arg = f
                        QtCore.QMetaObject.invokeMethod(self, "_next", Qt.QueuedConnection)

                    obj.add_done_callback(on_done)
                    return

                elif isinstance(obj, ProgressUpdate):
                    self.result_future.set_progress_range(0, obj.total)
                    self.result_future.set_progress(obj.current)
                    self.result_future.set_progress_text(obj.text)
                else:
                    raise RuntimeError("Generator yielded unknown object %s" % obj)

            except StopIteration:
                self.result_future.set_result(True)
                return
            except Exception as e:
                self.result_future.set_exception(e)
                self.apply_generator.close()
                return

def apply_setup(source, dest, device_registry):
    """
    source: a basic_model.MRCRegistry compatible object; usually a
            config_model.Setup instance.
    dest  : a basic_model.MRCRegistry compatible object; usually the root of
            the hardware tree.
    device_registry: a DeviceRegistry compatible object providing DeviceProfile
        instances by idc.
    """
    
    # * Compare structure of source and dest. Report
    #   missing/disconnected/silenced MRCs.
    #   Ignore additional MRCs in dest (XXX: or yield a warning?)
    #   Answers & reactions:
    #     missing: skip, abort, try again
    #     disconnected: skip, abort, try again
    #     silenced: skip, abort, try again
    #   - Compare the structure of the matching MRCs:
    #     Report missing devices, address conflicts and idc conflicts.
    #     Answers & reactions:
    #       missing: skip device, skip mrc, abort, try again
    #       addr conflict: skip bus, skip mrc, abort, try again
    #       idc conflict: skip device, skip mrc, abort, try again
    #
    # FIXME: where to add mrc connections and wait for them to be ready? in
    # here or do this before calling apply_setup?

    for src_mrc in source:
        dest_mrc = dest.get_mrc(src_mrc.url)

        for src_dev in src_mrc:
            dest_dev     = dest_mrc.get_device(src_dev.bus, src_dev.address)
            profile      = device_registry.get_profile(src_dev.idc)
            apply_config = apply_device_config(src_dev, dest_dev, profile)
            arg          = None

            while True:
                try:
                    obj = apply_config.send(arg)
                    arg = yield obj
                except StopIteration:
                    break
                except GeneratorExit:
                    apply_config.close()
                    return

class ApplySetupRunner(QtCore.QObject):
    def __init__(self, source, dest, device_registry, parent=None):
        super(ApplySetupRunner, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.source = source
        self.dest   = dest
        self.device_registry = device_registry

    def start(self):
        self.apply_generator = apply_setup(self.source, self.dest, self.device_registry)
        self.arg = None
        self.result_future = future.Future()
        QtCore.QMetaObject.invokeMethod(self, "_next", Qt.QueuedConnection)
        return self.result_future

    @pyqtSlot()
    def _next(self):
        while True:
            try:
                obj = self.apply_generator.send(self.arg)

                if isinstance(obj, future.Future):

                    def on_done(f):
                        self.arg = f
                        QtCore.QMetaObject.invokeMethod(self, "_next", Qt.QueuedConnection)

                    obj.add_done_callback(on_done)
                    return

                elif isinstance(obj, ProgressUpdate):
                    self.result_future.set_progress_range(0, obj.total)
                    self.result_future.set_progress(obj.current)
                    self.result_future.set_progress_text(obj.text)
                else:
                    raise RuntimeError("Generator yielded unknown object %s" % obj)

            except StopIteration:
                self.result_future.set_result(True)
                return
            except Exception as e:
                self.result_future.set_exception(e)
                self.apply_generator.close()
                return

if __name__ == "__main__":
    import mock
    import basic_model as bm
    import device_profile
    import devices.device_profile_mhv4
    import logging

    logging.basicConfig(level=logging.DEBUG,
            format='[%(asctime)-15s] [%(name)s.%(levelname)s] %(message)s')

    app = QtCore.QCoreApplication([])

    mhv4 = device_profile.from_dict(devices.device_profile_mhv4.profile_dict)

    source = mock.MagicMock()
    dest   = mock.MagicMock()

    source.idc = dest.idc = mhv4.idc

    def get_parameter(address):
        return bm.ResultFuture().set_result(bm.ReadResult(bus=0, device=0, address=address, value=42))

    set_values = dict()

    def set_parameter(address, value):
        set_values[address] = value
        return bm.ResultFuture().set_result(bm.SetResult(bus=0, device=0, address=address, value=value, requested_value=value))

    source.get_parameter.side_effect = get_parameter
    dest.set_parameter.side_effect = set_parameter

    runner = ApplyDeviceConfigRunner(source=source, dest=dest, device_profile=mhv4)
    runner.start()

    app.exec_()

    print set_values
