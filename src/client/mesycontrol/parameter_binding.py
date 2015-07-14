#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtGui

import basic_model as bm
import util
import future

class AbstractParameterBinding(object):
    def __init__(self, device, parameter_profile, display_mode, write_mode, target):
        """
        device: app_model.Device or DeviceBase subclass
        display_mode: util.HARDWARE | util.CONFIG
        write_mode: util.HARDWARE | util.CONFIG | util.COMBINED
        """
        self.device         = device
        self.profile        = parameter_profile
        self._display_mode  = display_mode
        self.write_mode     = write_mode
        self.target         = target

        self.device.hardware_set.connect(self._on_device_hw_set)
        self.device.config_set.connect(self._on_device_cfg_set)

        self._on_device_hw_set(self.device, None, self.device.hw)
        self._on_device_cfg_set(self.device, None, self.device.cfg)

    def populate(self):
        dev = self.device.cfg if self.display_mode == util.CONFIG else self.device.hw
        dev.get_parameter(self.address).add_done_callback(self._update)

    def get_address(self):
        return self.profile.address

    def get_display_mode(self):
        return self._display_mode

    def set_display_mode(self, mode):
        if self.display_mode != mode:
            self._display_mode = mode
            self.populate()

    address = property(fget=get_address)
    display_mode = property(fget=get_display_mode, fset=set_display_mode)

    def _on_device_hw_set(self, device, old_hw, new_hw):
        if old_hw is not None:
            old_hw.parameter_changed.disconnect(self._on_hw_parameter_changed)
            
        if new_hw is not None:
            new_hw.parameter_changed.connect(self._on_hw_parameter_changed)

    def _on_device_cfg_set(self, device, old_cfg, new_cfg):
        if old_cfg is not None:
            old_cfg.parameter_changed.disconnect(self._on_cfg_parameter_changed)

        if new_cfg is not None:
            new_cfg.parameter_changed.connect(self._on_cfg_parameter_changed)

    def _on_hw_parameter_changed(self, address, value):
        if address == self.address and self.display_mode == util.HARDWARE:
            self.device.hw.get_parameter(self.address).add_done_callback(self._update)

    def _on_cfg_parameter_changed(self, address, value):
        if address == self.address and self.display_mode == util.CONFIG:
            self.device.cfg.get_parameter(self.address).add_done_callback(self._update)

    def _write_value(self, value):
        if self.write_mode == util.COMBINED:

            def on_cfg_set(f):
                try:
                    if not f.exception():
                        self.device.hw.set_parameter(self.address, value
                                ).add_done_callback(self._update)
                    else:
                        self._update(f)
                except future.CancelledError:
                    pass

            self.device.cfg.set_parameter(self.address, value
                    ).add_done_callback(on_cfg_set)
        else:
            dev = self.device.cfg if self.write_mode == util.CONFIG else self.device.hw
            dev.set_parameter(self.address, value).add_done_callback(self._update)

    def _update(self, result_future):
        raise NotImplementedError()

    def _get_tooltip(self, result_future):
        tt  = "addr %d" % self.address

        if self.profile.is_named():
            tt += ", name=%s" % self.profile.name

        if not result_future.cancelled():
            if not result_future.exception():
                result = result_future.result()
                value  = int(result)

                tt += ", value=%d" % value

                if isinstance(result, bm.SetResult) and not result:
                    tt += ", requested_value=%d" % result.requested_value

                if len(self.profile.units) > 1:
                    unit = self.profile.units[1]
                    tt += ", %f%s" % (unit.unit_value(value), unit.label)
            else:
                tt += ", %s" % result_future.exception()

        return tt

class SpinBoxParameterBinding(AbstractParameterBinding):
    def __init__(self, device, profile, display_mode, write_mode, target):
        super(SpinBoxParameterBinding, self).__init__(device, profile, display_mode, write_mode, target)

        if profile.range is not None:
            target.setMinimum(profile.range[0])
            target.setMaximum(profile.range[1])

        if hasattr(target, 'delayed_valueChanged'):
            target.delayed_valueChanged.connect(self._value_changed)
        else:
            target.valueChanged.connect(self._value_changed)

    def _update(self, result_future):
        pal = QtGui.QApplication.palette()

        if not result_future.exception():
            # No exception. Check if set was ok in case of SetResult.
            result = result_future.result()
            value  = int(result)

            with util.block_signals(self.target):
                self.target.setValue(value)

            if isinstance(result, bm.SetResult) and not result:
                pal.setColor(QtGui.QPalette.Base, QtGui.QColor('red'))
        else:
            # Exception case
            pal.setColor(QtGui.QPalette.Base, QtGui.QColor('red'))

        self.target.setPalette(pal)
        self.target.setToolTip(self._get_tooltip(result_future))

    def _value_changed(self, value):
        self._write_value(value)

class DoubleSpinBoxParameterBinding(AbstractParameterBinding):
    def __init__(self, device, profile, display_mode, write_mode, unit_name, target):
        super(DoubleSpinBoxParameterBinding, self).__init__(device, profile, display_mode, write_mode, target)

        self.unit = profile.get_unit(unit_name)

        if profile.range is not None:
            target.setMinimum(self.unit.unit_value(profile.range[0]))
            target.setMaximum(self.unit.unit_value(profile.range[1]))

        if hasattr(target, 'delayed_valueChanged'):
            target.delayed_valueChanged.connect(self._value_changed)
        else:
            target.valueChanged.connect(self._value_changed)

    def _update(self, result_future):
        pal = QtGui.QApplication.palette()

        if not result_future.exception():
            # No exception. Check if set was ok in case of SetResult.
            result = result_future.result()
            value  = self.unit.unit_value(int(result))

            with util.block_signals(self.target):
                self.target.setValue(value)

            if isinstance(result, bm.SetResult) and not result:
                pal.setColor(QtGui.QPalette.Base, QtGui.QColor('red'))
        else:
            # Exception case
            pal.setColor(QtGui.QPalette.Base, QtGui.QColor('red'))

        self.target.setPalette(pal)
        self.target.setToolTip(self._get_tooltip(result_future))

    def _value_changed(self, dvalue):
        self._write_value(self.unit.raw_value(dvalue))

class Factory(object):
    def __init__(self):
        self.predicate_binding_class_pairs = list()
        self.classinfo_bindings = list()

    def append_predicate(self, predicate, binding_class):
        self.predicate_binding_class_pairs.append((predicate, binding_class))

    def insert_predicate(self, idx, predicate, binding_class):
        self.predicate_binding_class_pairs.insert(idx, (predicate, binding_class))

    def append_classinfo_binding(self, target_classinfo, binding_class):
        self.classinfo_bindings.append((target_classinfo, binding_class))

    def insert_classinfo_binding(self, idx, target_classinfo, binding_class):
        self.classinfo_bindings.insert(idx, (target_classinfo, binding_class))

    def get_binding_class(self, target_object):
        for pred, cls in self.predicate_binding_class_pairs:
            if pred(target_object):
                return cls

        for cls_info, cls in self.classinfo_bindings:
            if isinstance(target_object, cls_info):
                return cls

        return None

    def make_binding(self, **kwargs):
        cls = self.get_binding_class(kwargs['target'])

        if cls is not None:
            return cls(**kwargs)

        raise ValueError("Could not find binding class for target %s" % kwargs['target'])

factory = Factory()

factory.append_classinfo_binding(
        (util.DelayedSpinBox, QtGui.QSpinBox), SpinBoxParameterBinding)

factory.append_classinfo_binding(
        (util.DelayedDoubleSpinBox, QtGui.QDoubleSpinBox), DoubleSpinBoxParameterBinding)

if __name__ == "__main__":
    import mock

    app = QtGui.QApplication([])

    device = mock.MagicMock()
    profile = mock.MagicMock()
    display_mode = util.CONFIG
    write_mode = util.COMBINED
    target = QtGui.QSpinBox()

    d = dict(device=device)

    binding = factory.make_binding(device=device, profile=profile, display_mode=display_mode,
            write_mode=write_mode, target=target)

    target2 = util.DelayedDoubleSpinBox()
    binding2 = factory.make_binding(device=device, profile=profile, display_mode=display_mode,
            write_mode=write_mode, unit_name="the_unit_name", target=target2)

    target.show()
    target2.show()

    app.exec_()

    print device.mock_calls
    print profile.mock_calls
