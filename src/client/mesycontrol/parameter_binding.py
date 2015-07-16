#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtGui

import logging

import basic_model as bm
import util
import future

log = logging.getLogger(__name__)

class AbstractParameterBinding(object):
    def __init__(self, device, profile, target, display_mode, write_mode=None):
        """
        device: app_model.Device or DeviceBase subclass
        display_mode: util.HARDWARE | util.CONFIG
        write_mode: util.HARDWARE | util.CONFIG | util.COMBINED
        """
        self.device         = device
        self.profile        = profile
        self._display_mode  = display_mode
        self.write_mode     = write_mode if write_mode is not None else display_mode
        self.target         = target
        self._update_callbacks = list()

        self.device.hardware_set.connect(self._on_device_hw_set)
        self.device.config_set.connect(self._on_device_cfg_set)

        self._on_device_hw_set(self.device, None, self.device.hw)
        self._on_device_cfg_set(self.device, None, self.device.cfg)

    def populate(self):
        """Gets the value of this bindings parameter and updates the target
        display once the value is retrieved."""
        dev = self.device.cfg if self.display_mode == util.CONFIG else self.device.hw
        f = dev.get_parameter(self.address).add_done_callback(self._update_wrapper)
        log.debug("populate: addr=%d, future=%s", self.address, f)

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

    def add_update_callback(self, cb):
        self._update_callbacks.append(cb)

    def _on_device_hw_set(self, device, old_hw, new_hw):
        if old_hw is not None:
            old_hw.parameter_changed.disconnect(self._on_hw_parameter_changed)
            old_hw.connected.disconnect(self.populate)
            
        if new_hw is not None:
            new_hw.parameter_changed.connect(self._on_hw_parameter_changed)
            new_hw.connected.connect(self.populate)

    def _on_device_cfg_set(self, device, old_cfg, new_cfg):
        if old_cfg is not None:
            old_cfg.parameter_changed.disconnect(self._on_cfg_parameter_changed)

        if new_cfg is not None:
            new_cfg.parameter_changed.connect(self._on_cfg_parameter_changed)

    def _on_hw_parameter_changed(self, address, value):
        if address == self.address and self.display_mode == util.HARDWARE:
            f = self.device.hw.get_parameter(self.address).add_done_callback(self._update_wrapper)
            log.debug("_on_hw_parameter_changed: addr=%d, future=%s", self.address, f)

    def _on_cfg_parameter_changed(self, address, value):
        if address == self.address and self.display_mode == util.CONFIG:
            f = self.device.cfg.get_parameter(self.address).add_done_callback(self._update_wrapper)
            log.debug("_on_cfg_parameter_changed: addr=%d, future=%s", self.address, f)

    def _write_value(self, value):
        log.debug("_write_value: %d=%d", self.address, value)

        if self.write_mode == util.COMBINED:

            def on_cfg_set(f):
                try:
                    if not f.exception():
                        self.device.hw.set_parameter(self.address, value
                                ).add_done_callback(self._update_wrapper)
                    else:
                        self._update_wrapper(f)
                except future.CancelledError:
                    pass

            self.device.cfg.set_parameter(self.address, value
                    ).add_done_callback(on_cfg_set)
        else:
            dev = self.device.cfg if self.write_mode == util.CONFIG else self.device.hw
            dev.set_parameter(self.address, value).add_done_callback(self._update_wrapper)

    def _update_wrapper(self, result_future):
        log.debug("_update_wrapper: addr=%d, result_future=%s", self.address, result_future)
        self._update(result_future)

        for cb in self._update_callbacks:
            try:
                cb(result_future)
            except Exception as e:
                log.warning("update callback raised %s: %s", type(e), e)

    def _update(self, result_future):
        raise NotImplementedError()

    def _get_tooltip(self, result_future):
        tt  = ("name=%s, " % self.profile.name) if self.profile.is_named() else str()
        tt += "addr=%d" % self.address

        if result_future.cancelled():
            return tt

        if result_future.exception() is not None:
            e = result_future.exception()
            tt += ", exc=%s: %s" % (type(e).__name__, e)
        else:
            result = result_future.result()
            value  = int(result)

            tt += ", value=%d" % value

            if isinstance(result, bm.SetResult) and not result:
                tt += ", requested_value=%d" % result.requested_value

            if len(self.profile.units) > 1:
                unit = self.profile.units[1]
                tt += ", %f%s" % (unit.unit_value(value), unit.label)

        return tt

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

class DefaultParameterBinding(AbstractParameterBinding):
    def __init__(self, **kwargs):
        super(DefaultParameterBinding, self).__init__(**kwargs)

    def _update(self, result_future):
        pal = QtGui.QApplication.palette()

        try:
            result = result_future.result()
            if isinstance(result, bm.SetResult) and not result:
                raise RuntimeError()
        except Exception:
            pal.setColor(QtGui.QPalette.Base, QtGui.QColor('red'))

        self.target.setPalette(pal)
        self.target.setToolTip(self._get_tooltip(result_future))
        self.target.setStatusTip(self.target.toolTip())

class SpinBoxParameterBinding(DefaultParameterBinding):
    def __init__(self, **kwargs):
        super(SpinBoxParameterBinding, self).__init__(**kwargs)

        if self.profile.range is not None:
            with util.block_signals(self.target):
                self.target.setMinimum(self.profile.range[0])
                self.target.setMaximum(self.profile.range[1])

        if hasattr(self.target, 'delayed_valueChanged'):
            self.target.delayed_valueChanged.connect(self._value_changed)
        else:
            self.target.valueChanged.connect(self._value_changed)

    def _update(self, result_future):
        log.debug("SpinBoxParameterBinding: addr=%d, result_future=%s", self.address, result_future)
        super(SpinBoxParameterBinding, self)._update(result_future)

        try:
            with util.block_signals(self.target):
                self.target.setValue(int(result_future.result()))
        except Exception:
            pass

    def _value_changed(self, value):
        log.debug("SpinBoxParameterBinding: addr=%d: _value_changed: %d", self.address, value)
        self._write_value(value)

class DoubleSpinBoxParameterBinding(DefaultParameterBinding):
    def __init__(self, unit_name, **kwargs):
        super(DoubleSpinBoxParameterBinding, self).__init__(**kwargs)

        self.unit = self.profile.get_unit(unit_name)

        if self.profile.range is not None:
            with util.block_signals(self.target):
                self.target.setMinimum(self.unit.unit_value(profile.range[0]))
                self.target.setMaximum(self.unit.unit_value(profile.range[1]))

        if hasattr(self.target, 'delayed_valueChanged'):
            self.target.delayed_valueChanged.connect(self._value_changed)
        else:
            self.target.valueChanged.connect(self._value_changed)

    def _update(self, result_future):
        super(DoubleSpinBoxParameterBinding, self)._update(result_future)
        try:
            value = self.unit.unit_value(int(result_future.result()))
            with util.block_signals(self.target):
                self.target.setValue(value)
        except Exception:
            pass

    def _value_changed(self, dvalue):
        self._write_value(self.unit.raw_value(dvalue))

class LabelParameterBinding(DefaultParameterBinding):
    def __init__(self, unit_name, prec=2, **kwargs):
        super(LabelParameterBinding, self).__init__(**kwargs)

        self.unit = self.profile.get_unit(unit_name)

    def _update(self, result_future):
        super(LabelParameterBinding, self)._update(result_future)
        try:
            value = self.unit.unit_value(int(result_future))
            self.target.setText("%.2f%s" % (value, self.unit.label))
        except Exception:
            self.target.setText("N/A")

class CheckBoxParameterBinding(DefaultParameterBinding):
    def __init__(self, **kwargs):
        super(CheckBoxParameterBinding, self).__init__(**kwargs)
        self.target.clicked[bool].connect(self._value_changed)

    def _update(self, result_future):
        super(CheckBoxParameterBinding, self)._update(result_future)
        try:
            with util.block_signals(self.target):
                self.target.setChecked(int(result_future))
        except Exception:
            pass

    def _value_changed(self, on_off):
        self._write_value(on_off)

class ComboBoxParameterBinding(DefaultParameterBinding):
    def __init__(self, **kwargs):
        super(ComboBoxParameterBinding, self).__init__(**kwargs)
        self.target.currentIndexChanged[int].connect(self._write_value)

    def _update(self, rf):
        super(ComboBoxParameterBinding, self)._update(rf)
        try:
            with util.block_signals(self.target):
                self.target.setCurrentIndex(int(rf))
        except Exception:
            pass

factory = Factory()

factory.append_classinfo_binding(
        (util.DelayedSpinBox, QtGui.QSpinBox), SpinBoxParameterBinding)

factory.append_classinfo_binding(
        (util.DelayedDoubleSpinBox, QtGui.QDoubleSpinBox), DoubleSpinBoxParameterBinding)

factory.append_classinfo_binding(
        QtGui.QLabel, LabelParameterBinding)

factory.append_classinfo_binding(
        QtGui.QCheckBox, CheckBoxParameterBinding)

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
