import enum
import types
import itertools
from weakref import WeakSet
from types import FunctionType

from nagisa.core.state.config import cfg_property
from nagisa.core.functools import adapt, make_function
from .meter_base import build_meter
from ._registries import MeterRegistry


class _EnumMixin(object):
    @classmethod
    def _missing_(cls, value: str):
        return cls.__members__[value.upper()]


class BaseMeterGroupMeta(type):
    def __new__(mcls, name, bases, namespace, **kwargs):
        scope_names = namespace.get("_DEFINED_SCOPES", None)

        if scope_names is not None:
            scope_names = list(map(str.upper, scope_names))
            scope_enum_class = enum.Enum(
                "DefinedScopes",
                scope_names,
                type=_EnumMixin,
            )
            scope_enum_class.DEFAULT = scope_enum_class(scope_names[0])
            namespace["Scope"] = scope_enum_class

            for scope_name in scope_names:
                func_name = f"reset_{scope_name.lower()}"
                namespace[func_name] = make_function(
                    func_name,
                    f"""
                    def {func_name}(self):
                        self.reset(self.Scope.{scope_name})
                    """,
                )

        for attr_name in list(namespace):
            if attr_name.startswith('update_'):
                group_name = attr_name[len('update_'):]
                if group_name:
                    func_name = f'compute_{group_name}'
                    namespace[func_name] = make_function(
                        func_name,
                        f"""
                        def {func_name}(self):
                            return self.compute("{group_name}")
                        """,
                    )

        cls = super().__new__(mcls, name, bases, namespace, **kwargs)
        return cls


_meter_initializer_types = (tuple, type, str, FunctionType)


class BaseMeterGroup(metaclass=BaseMeterGroupMeta):

    _DEFINED_SCOPES = ("epoch", "iter")

    def __init__(self, cfg=None):
        self._cfg = cfg
        self.groups = {}
        self.group_metas = {}
        self.group_spec = {}
        self.scope_refs = {k: WeakSet() for k in self.Scope}

    cfg = cfg_property

    def _define_scope(self, meter, scope):
        scope = self.Scope(scope)
        self.scope_refs[scope].add(meter)

    def has_group(self, group_name):
        return group_name in self.groups

    def remove_group(self, group_name):
        del self.groups[group_name]
        return self

    def add_group(self, group_name, signature, spec):
        if self.has_group(group_name):
            assert spec is None or set(spec) == set(self.groups)
            return

        self.groups[group_name] = meters = {}
        for meter_key, spec_item in spec.items():

            assert (
                isinstance(spec_item, list) and 1 <= len(spec_item) <= 3
                or isinstance(spec_item, _meter_initializer_types)
            )

            if isinstance(spec_item, _meter_initializer_types):
                spec_item = [spec_item]

            if len(spec_item) == 1:
                init = spec_item[0]
                mapping = ...
                scope = self.Scope.DEFAULT
            elif len(spec_item) == 2:
                init, mapping = spec_item
                scope = self.Scope.DEFAULT
            else:
                init, mapping, scope = spec_item

            if mapping is ...:
                mapping = {'args': signature}
            elif isinstance(mapping, list):
                mapping = {'args': mapping}
            elif (isinstance(mapping, dict)
                  and not set(mapping).issubset({'args', 'kwargs'})):
                mapping = {'kwargs': mapping}

            assert isinstance(init, _meter_initializer_types)
            if isinstance(init, tuple):
                meter_cls, *init_args = init
            else:
                meter_cls = init
                init_args = ()

            meter = build_meter(meter_cls, init_args)
            meter.adapted_update = adapt(signature, meter.update, **mapping)
            self._define_scope(meter, scope)
            meters[meter_key] = meter

        return self

    def update(self, group_name, *, inputs=None, spec=None, **kwargs):
        if inputs is not None:
            assert isinstance(inputs, dict)
            assert not kwargs
            kwargs = inputs

        if not self.has_group(group_name):
            assert isinstance(spec, dict)
            self.add_group(group_name, list(kwargs.keys()), spec)

        for meter in self.groups[group_name].values():
            meter.adapted_update(**kwargs)

        return self

    def compute(self, group_name=None):
        if group_name is None:
            return {
                group_name: self.compute(group_name)
                for group_name in self.groups
            }

        result = {}
        for meter_key, meter in self.groups[group_name].items():
            result[meter_key] = meter.compute()

        return result

    def reset(self, scope=None):
        if scope is None:
            for scope in self.Scope:
                self.reset(scope)
            return self

        scope = self.Scope(scope)
        for meter in self.scope_refs[scope]:
            meter.reset()
        return self

    def reset_group(self, group_name=None):
        for meter in self.groups[group_name].values():
            meter.reset()


class DefaultMeterGroup(BaseMeterGroup):
    def update_loss(self, inputs):

        if not self.has_group("loss"):
            spec = {
                key: ["builtin.Avg", [f"i.{key}"], self.Scope.DEFAULT]
                for key in inputs
            }
            self.add_group("loss", ["i"], spec)

        self.update("loss", i=inputs)
        return self

    def update_time(self, inputs):
        if not self.has_group("time"):
            spec = {
                key: ["builtin.Avg", [f"i.{key}"], self.Scope.DEFAULT]
                for key in inputs
            }
            self.add_group("time", ["i"], spec)

        self.update("time", i=inputs)
        return self

    def update_metrics(self, outputs, targets, spec=None):
        self.update(
            "metrics",
            inputs={
                "outputs": outputs,
                "o": outputs,
                "targets": targets,
                "t": targets
            },
            spec=spec
        )
        return self