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
    # TODO: write doc, describe generator protocol
    # TODO: Store polling state and disable polling -> imho the caller should handle this
    # TODO: Enable RC

    try:
        if source.idc != dest.idc:
            raise RuntimeError("idc conflict between source and dest")

        if source.idc != device_profile.idc:
            raise RuntimeError("idc conflict between source and device profile")


        non_criticals   = device_profile.get_non_critical_config_parameters()
        criticals       = device_profile.get_critical_parameters()
        values          = dict()
        progress        = ProgressUpdate(current=0,
                total=2 * len(non_criticals) + 3 * len(criticals))

        yield progress

        progress.text = "Reading from source"

        # Read from source before touching dest.
        for pp in itertools.chain(non_criticals, criticals):
            f = yield source.get_parameter(pp.address)

            values[pp.address] = int(f)

            yield progress.increment()

        if len(criticals):
            progress.text = "Setting critical parameters to safe values"

        # Source params are available. Start modifying dest.
        # Set safe values for critical parameters.
        for pp in criticals:
            f = yield dest.set_parameter(pp.address, pp.safe_value)

            if int(f) != pp.safe_value:
                raise SetParameterError(f.result())

            yield progress.increment()

        progress.text = "Writing to destination"

        # Set non-criticals
        for pp in non_criticals:
            value = values[pp.address]

            f = yield dest.set_parameter(pp.address, value)

            if int(f) != value:
                raise SetParameterError(f.result())

            yield progress.increment()

        if len(criticals):
            progress.text = "Writing critical parameters to destination"

        # Finally set criticals to their config values
        for pp in criticals:
            value = values[pp.address]

            f = yield dest.set_parameter(pp.address, value)

            if int(f) != value:
                raise SetParameterError(f.result())

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
    # If the apply_device_config generator yields a Future object that is
    # completed a callback added via add_done_callback() will be executed
    # immediately. If _next() would be called directly from that callback this
    # can lead to exceeding the maximum call stack recursion depth.
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

            except SetParameterError as e:
                self.result_future.set_exception(e)
                self.apply_generator.close()
                return
            except StopIteration:
                self.result_future.set_result(True)
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

    pass


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
