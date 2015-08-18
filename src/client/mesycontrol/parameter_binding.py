#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import QtGui

import collections
import logging
import traceback
import weakref

import basic_model as bm
import util
import future

log = logging.getLogger(__name__)

class ReadWriteProfile(collections.namedtuple('ReadWriteProfile', 'read write')):
    def get_unit(self, unit_name):
        return self.write.get_unit(unit_name)

    def get_range(self):
        return self.write.range

    def get_units(self):
        return self.write.units

    range = property(get_range)
    units = property(get_units)

class ParameterUnavailable(Exception):
    def __init__(self, *args, **kwargs):
        super(ParameterUnavailable, self).__init__("Parameter not available", *args, **kwargs)

class AbstractParameterBinding(object):
    def __init__(self, device, profile, target, display_mode, write_mode=None, fixed_modes=False, **kwargs):
        """
        device: app_model.Device or DeviceBase subclass
        profile: parameter profile
        target: any class instance or None
        display_mode: util.HARDWARE | util.CONFIG
        write_mode: util.HARDWARE | util.CONFIG | util.COMBINED
        fixed_modes: If True set_display_mode() and set_write_mode() won't have any effect.
                     Use this to create e.g. hardware only bindings.
        """
        self._device        = weakref.ref(device)
        self.profile        = profile
        self._display_mode  = display_mode
        self._write_mode    = write_mode if write_mode is not None else display_mode
        self.target         = target
        self.fixed_modes    = fixed_modes
        self._update_callbacks = list()
        self._update_method_callbacks = list()

        self.device.hardware_set.connect(self._on_device_hw_set)
        self.device.config_set.connect(self._on_device_cfg_set)

        self._on_device_hw_set(self.device, None, self.device.hw)
        self._on_device_cfg_set(self.device, None, self.device.cfg)

    def populate(self):
        """Gets the value of this bindings parameter and updates the target
        display once the value is retrieved."""

        if not self.has_rw_profile() and self.display_mode == util.CONFIG and self.profile.read_only:
            # read-only parameters are never stored in the config
            self._update_wrapper(future.Future().set_exception(
                ParameterUnavailable("read_only parameter %s (%d) not stored in config" % (
                    self.profile.name, self.profile.address))))
            return

        # For RW parameters the read address is used if hardware is present
        # otherwise the write address is used as only that is actually stored
        # in the config.
        dev     = self.device.cfg if self.display_mode == util.CONFIG else self.device.hw

        if dev is None:
            self._update_wrapper(future.Future().set_exception(
                ParameterUnavailable("device is None")))
            return

        address = self.read_address if dev is self.device.hw else self.write_address
        f       = dev.get_parameter(address).add_done_callback(self._update_wrapper)
        log.debug("populate: target=%s, addr=%d, future=%s", self.target, address, f)

    def get_address(self):
        return self.profile.address

    def get_read_address(self):
        try:
            return self.profile.read.address
        except AttributeError:
            return self.address

    def get_write_address(self):
        try:
            return self.profile.write.address
        except AttributeError:
            return self.address

    def get_write_mode(self):
        return self._write_mode

    def set_write_mode(self, mode):
        if self.fixed_modes:
            return False

        self._write_mode = mode
        return True

    def get_display_mode(self):
        return self._display_mode

    def set_display_mode(self, mode):
        if self.fixed_modes:
            return False

        if self.display_mode != mode:
            self._display_mode = mode
            self.populate()

        return True

    def get_device(self):
        return self._device()

    def has_rw_profile(self):
        return isinstance(self.profile, ReadWriteProfile)

    def get_read_profile(self):
        if self.has_rw_profile():
            return self.profile.read
        return self.profile

    def get_write_profile(self):
        if self.has_rw_profile():
            return self.profile.write
        return self.profile

    device          = property(fget=get_device)
    address         = property(fget=get_address)
    read_address    = property(fget=get_read_address)
    write_address   = property(fget=get_write_address)
    display_mode    = property(
            fget=lambda self: self.get_display_mode(),
            fset=lambda self, v: self.set_display_mode(v))
    write_mode      = property(fget=get_write_mode, fset=set_write_mode)
    read_profile    = property(fget=get_read_profile)
    write_profile   = property(fget=get_write_profile)

    def add_update_callback(self, method_or_func, *args, **kwargs):
        """Adds a callback to be invoked when this binding updates its target.

        The callback will be called with the result_future that caused the
        update as its first argument and the optional args and kwargs as the
        following arguments.

        If the given method_or_func is a bound method a weak reference to the
        corresponding object will be stored. This way the parameter binding
        won't keep any objects alive just because they're registered as a
        callback.

        http://stackoverflow.com/questions/1673483/how-to-store-callback-methods
        """
        if hasattr(method_or_func, 'im_self'):
            obj  = method_or_func.im_self
            meth = method_or_func.im_func.__name__
            self._update_callbacks.append((weakref.ref(obj), meth, args, kwargs))
        else:
            self._update_callbacks.append((method_or_func, args, kwargs))

        return self

    def _exec_callbacks(self, result_future):
        for tup in self._update_callbacks:
            try:
                if len(tup) == 3:
                    func, args, kwargs = tup
                    func(result_future, *args, **kwargs)
                else:
                    obj_ref, meth, args, kwargs = tup
                    getattr(obj_ref(), meth)(result_future, *args, **kwargs)

            except Exception as e:
                log.warning("target=%s, update callback raised %s: %s", self.target, type(e), e)
                traceback.print_exc()

    def _on_device_hw_set(self, device, old_hw, new_hw):
        if old_hw is not None:
            old_hw.parameter_changed.disconnect(self._on_hw_parameter_changed)
            old_hw.disconnected.disconnect(self.populate)
            old_hw.connected.disconnect(self.populate)
            
        if new_hw is not None:
            new_hw.parameter_changed.connect(self._on_hw_parameter_changed)
            new_hw.disconnected.connect(self.populate)
            new_hw.connected.connect(self.populate)

    def _on_device_cfg_set(self, device, old_cfg, new_cfg):
        if old_cfg is not None:
            old_cfg.parameter_changed.disconnect(self._on_cfg_parameter_changed)

        if new_cfg is not None:
            new_cfg.parameter_changed.connect(self._on_cfg_parameter_changed)

    def _on_hw_parameter_changed(self, address, value):
        if address == self.read_address and self.display_mode == util.HARDWARE:
            f = self.device.hw.get_parameter(self.read_address).add_done_callback(self._update_wrapper)
            log.debug("_on_hw_parameter_changed: target=%s, addr=%d, future=%s", self.target, self.read_address, f)

    def _on_cfg_parameter_changed(self, address, value):
        if address == self.write_address and self.display_mode == util.CONFIG:
            f = self.device.cfg.get_parameter(self.write_address).add_done_callback(self._update_wrapper)
            log.debug("_on_cfg_parameter_changed: target=%s, addr=%d, future=%s", self.target, self.write_address, f)

    def _write_value(self, value):
        log.debug("_write_value: target=%s, %d=%d", self.target, self.write_address, value)

        if self.has_rw_profile():
            self._write_value_rw(value)
            return

        # Profile has a single address
        if self.profile.read_only:
            raise RuntimeError("Attempting to write to a read-only address")

        if self.write_mode == util.COMBINED:
            def on_cfg_set(f):
                try:
                    if f.exception() is None:
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

    def _write_value_rw(self, value):
        # Profile is split into read and write addresses.

        if self.write_mode == util.CONFIG:
            self.device.cfg.set_parameter(self.write_address, value
                    ).add_done_callback(self._update_wrapper)

        elif self.write_mode == util.HARDWARE:
            self.device.hw.set_parameter(self.write_address, value
                    ).add_done_callback(self._update_wrapper)

        elif self.write_mode == util.COMBINED:
            def on_cfg_set(f_cfg_set):
                if f_cfg_set.cancelled():
                    return

                if (f_cfg_set.exception() is not None or
                        (isinstance(f_cfg_set.result(), bm.SetResult) and
                            not f_cfg_set.result())):
                    self._update_wrapper(f_cfg_set)
                    return

                self.device.hw.set_parameter(self.write_address, value
                        ).add_done_callback(self._update_wrapper)

            self.device.cfg.set_parameter(self.write_address, value
                    ).add_done_callback(on_cfg_set)

    def _update_wrapper(self, result_future):
        log.debug("_update_wrapper: target=%s, addr=%d, result_future=%s",
                self.target, self.read_address, result_future)

        self._update(result_future)
        self._exec_callbacks(result_future)

    def _update(self, result_future):
        """This method will be passed the Future of the last operation that
        should result in an update to this bindings target.

        The result_future will in most cases contain either a ReadResult or a
        SetResult depending on which operation triggered the update.

        In case of a hardware-only parameter without any connected hardware a
        ParameterUnavailable instance will be set in result_future."""
        raise NotImplementedError()

    def _get_tooltip(self, result_future):
        if self.has_rw_profile():
            tt  = "name=(r=%s,w=%s), " % (self.profile.read.name, self.profile.write.name)
            tt += "addr=(r=%d,w=%d)" % (self.read_address, self.write_address)
        else:
            tt  = "name=%s, " % self.profile.name
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
                tt += ", %f %s" % (unit.unit_value(value), QtCore.QString.fromUtf8(unit.label))

        return tt

class DefaultParameterBinding(AbstractParameterBinding):
    def __init__(self, **kwargs):
        super(DefaultParameterBinding, self).__init__(**kwargs)
        self.log = util.make_logging_source_adapter(__name__, self)
        if isinstance(self.target, QtGui.QWidget):
            self._original_palette = QtGui.QPalette(self.target.palette())

    def _update(self, result_future):
        self.log.debug("_update: target=%s, result_future=%s", self.target, result_future)

        pal = self._get_palette(result_future)
        self.target.setPalette(pal)
        self.target.setToolTip(self._get_tooltip(result_future))
        self.target.setStatusTip(self.target.toolTip())
        self.target.setEnabled(not isinstance(result_future.exception(), ParameterUnavailable))

    def _get_palette(self, rf):
        pal = QtGui.QPalette(self._original_palette)

        try:
            result = rf.result()
            if isinstance(result, bm.SetResult) and not result:
                raise RuntimeError()
        except Exception:
            pal.setColor(QtGui.QPalette.Base, QtGui.QColor('red'))

        return pal

class TargetlessParameterBinding(AbstractParameterBinding):
    """Usefull if there's no target widget but the add_update_callback()
    functionality is needed."""
    def __init__(self, **kwargs):
        super(TargetlessParameterBinding, self).__init__(target=None, **kwargs)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.log.debug("TargetlessParameterBinding: kwargs: %s", kwargs)

    def set_display_mode(self, mode):
        self.log.debug("TargetlessParameterBinding: set_display_mode %s", util.RW_MODE_NAMES[mode])
        if mode == util.CONFIG:
            import traceback
            traceback.print_stack()
        super(TargetlessParameterBinding, self).set_display_mode(mode)

    def set_write_mode(self, mode):
        self.log.debug("TargetlessParameterBinding: set_write_mode %s", util.RW_MODE_NAMES[mode])
        super(TargetlessParameterBinding, self).set_write_mode(mode)

    def _update(self, result_future):
        self.log.debug("TargetlessParameterBinding: _update rf=%s, display_mode=%s",
                result_future, util.RW_MODE_NAMES[self.display_mode])
        pass

class SpinBoxParameterBinding(DefaultParameterBinding):
    def __init__(self, **kwargs):
        super(SpinBoxParameterBinding, self).__init__(**kwargs)

        if self.profile.range is not None:
            with util.block_signals(self.target):
                self.target.setMinimum(self.profile.range[0])
                self.target.setMaximum(self.profile.range[1])

        if hasattr(self.target, 'delayed_valueChanged'):
            self.target.delayed_valueChanged.connect(self._write_value)
        else:
            self.target.valueChanged.connect(self._write_value)

    def _update(self, result_future):
        log.debug("SpinBoxParameterBinding: addr=%d, result_future=%s", self.address, result_future)
        super(SpinBoxParameterBinding, self)._update(result_future)

        try:
            with util.block_signals(self.target):
                self.target.setValue(int(result_future.result()))
        except Exception:
            pass

class DoubleSpinBoxParameterBinding(DefaultParameterBinding):
    def __init__(self, unit_name, **kwargs):
        super(DoubleSpinBoxParameterBinding, self).__init__(**kwargs)

        self.unit = self.profile.get_unit(unit_name)

        if self.profile.range is not None:
            with util.block_signals(self.target):
                self.target.setMinimum(self.unit.unit_value(self.profile.range[0]))
                self.target.setMaximum(self.unit.unit_value(self.profile.range[1]))

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
        self.target.clicked[bool].connect(self._write_value)

    def _update(self, result_future):
        super(CheckBoxParameterBinding, self)._update(result_future)
        try:
            with util.block_signals(self.target):
                self.target.setChecked(int(result_future))
        except Exception:
            pass

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

class RadioButtonGroupParameterBinding(DefaultParameterBinding):
    def __init__(self, **kwargs):
        super(RadioButtonGroupParameterBinding, self).__init__(**kwargs)
        self.target.buttonClicked[int].connect(self._on_button_clicked)

    def _on_button_clicked(self, button_id):
        self._write_value(button_id)

    def _update(self, rf):
        self.target.button(int(rf)).setChecked(True)

        for b in self.target.buttons():
            b.setToolTip(self._get_tooltip(rf))
            b.setStatusTip(b.toolTip())

    @staticmethod
    def predicate(target):
        return (isinstance(target, QtGui.QButtonGroup) and
                all(isinstance(b, QtGui.QRadioButton) for b in target.buttons()))

class LCDNumberParameterBinding(DefaultParameterBinding):
    def __init__(self, unit_name=None, precision=2, **kwargs):
        super(LCDNumberParameterBinding, self).__init__(**kwargs)
        self.unit_name = unit_name
        self.precision = precision

    def _update(self, rf):
        super(LCDNumberParameterBinding, self)._update(rf)
        try:
            if self.unit_name is None:
                self.target.display(str(int(rf)))
            else:
                unit  = self.profile.get_unit(self.unit_name)
                value = unit.unit_value(int(rf))
                text  = "%%.%df" % self.precision
                text  = text % value
                self.target.display(text)
        except Exception:
            pass

class SliderParameterBinding(DefaultParameterBinding):
    def __init__(self, unit_name=None, update_on='value_changed', **kwargs):
        """update_on = value_changed | slider_released
        """
        super(SliderParameterBinding, self).__init__(**kwargs)

        self.unit = self.profile.get_unit(unit_name) if unit_name is not None else None

        if update_on == 'value_changed':
            self.target.valueChanged.connect(self._value_changed)
        elif update_on == 'slider_released':
            self.target.sliderReleased.connect(self._slider_released)
        else:
            raise ValueError("invalid value for 'update_on': %s" % update_on)

    def _update(self, rf):
        super(SliderParameterBinding, self)._update(rf)
        if self.unit is None:
            self.target.setValue(int(rf))
        else:
            value = self.unit.unit_value(int(rf))
            self.target.setValue(value)

    def _value_changed(self, dvalue):
        self._write_value(self.unit.raw_value(dvalue))

    def _slider_released(self):
        self._write_value(self.unit.raw_value(self.target.value()))

class Factory(object):
    def __init__(self):
        self.predicate_binding_class_pairs = list()
        self.classinfo_bindings = list()

    def append_predicate_binding(self, predicate, binding_class):
        self.predicate_binding_class_pairs.append((predicate, binding_class))

    def insert_predicate_binding(self, idx, predicate, binding_class):
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
        cls = self.get_binding_class(kwargs.get('target', None))

        if cls is not None:
            try:
                return cls(**kwargs)
            except Exception as e:
                e.args = e.args + ("class=%s, kwargs=%s" % (cls.__name__, kwargs),)
                raise

        raise ValueError("Could not find binding class for target %s" % kwargs['target'])

factory = Factory()

factory.append_classinfo_binding(
        (util.DelayedSpinBox, QtGui.QSpinBox), SpinBoxParameterBinding)

factory.append_classinfo_binding(
        (util.DelayedDoubleSpinBox, QtGui.QDoubleSpinBox), DoubleSpinBoxParameterBinding)

factory.append_classinfo_binding(
        QtGui.QLabel, LabelParameterBinding)

factory.append_classinfo_binding(
        QtGui.QCheckBox, CheckBoxParameterBinding)

factory.append_classinfo_binding(
        QtGui.QComboBox, ComboBoxParameterBinding)

factory.append_predicate_binding(
        RadioButtonGroupParameterBinding.predicate, RadioButtonGroupParameterBinding)

factory.append_classinfo_binding(
        QtGui.QLCDNumber, LCDNumberParameterBinding)

factory.append_classinfo_binding(
        QtGui.QSlider, SliderParameterBinding)

factory.append_predicate_binding(
        lambda target: target is None, TargetlessParameterBinding)

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
