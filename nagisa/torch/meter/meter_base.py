import abc
import functools
from typing import Callable, Any
from collections.abc import Iterable

from nagisa.torch.misc import comm
from nagisa.torch.misc import numeric_typing as nt
from nagisa.core.misc.naming import camel_to_snake
from ._registries import MeterRegistry


def build_meter(meter_cls, init_args):
    meter_cls = MeterRegistry.get(meter_cls, meter_cls)
    if not is_meter_class(meter_cls) and not callable(meter_cls):
        raise RuntimeError  # TODO
    return meter_cls(*init_args)


def is_meter_class(C) -> bool:
    return isinstance(C, type) and issubclass(C, MeterBase)


class MeterMeta(abc.ABCMeta):
    def __new__(mcls, name, bases, namespace, **kwargs):
        for attr_name, attr in namespace.items():
            if getattr(attr, "_decorated", False):
                continue

            if callable(attr):
                if getattr(attr, "reinit__is_reduced", False):
                    attr = reinit__is_reduced(attr)
                if hasattr(attr, "sync_all_reduce"):
                    attr = sync_all_reduce(attr.sync_all_reduce)(attr)

            namespace[attr_name] = attr

        cls = super().__new__(mcls, name, bases, namespace, **kwargs)
        return cls


class MeterBase(metaclass=MeterMeta):
    def __init__(self):
        self._is_reduced = True

    @abc.abstractmethod
    def reset(self) -> None:
        pass

    @abc.abstractmethod
    def update(self, output) -> None:
        pass

    @abc.abstractmethod
    def compute(self) -> Any:
        pass

    def __init_subclass__(cls, key=None):

        if key is None:
            keys = [camel_to_snake(cls.__name__), cls.__name__]
        elif isinstance(key, str):
            keys = [key]
        else:
            assert isinstance(key, (list, tuple))
            keys = key

        for key in keys:
            MeterRegistry.register(key, cls)

    @classmethod
    def __subclasshook__(cls, C):
        expected_methods = ("reset", "update", "compute")
        if cls is MeterBase:
            for B in C.__mro__:
                if all(callable(B.__dict__.get(fname))
                       for fname in expected_methods):
                    return True
            return False
        return NotImplemented


def sync_all_reduce(*attrs) -> Callable:
    """Helper decorator for distributed configuration to collect instance attribute value
    across all participating processes.
    See :doc:`metrics` on how to use it.
    Args:
        *attrs: attribute names of decorated class
    """
    def wrapper(func: Callable) -> Callable:
        @functools.wraps(func)
        def another_wrapper(self: MeterBase, *args, **kwargs) -> Callable:
            if not isinstance(self, MeterBase):
                raise RuntimeError(
                    "Decorator sync_all_reduce should be used on ignite.metric.Metric class methods only"
                )

            if len(attrs) > 0 and not self._is_reduced:
                for attr in attrs:
                    t = getattr(self, attr, None)
                    if t is not None and comm.get_world_size() > 1:
                        t = comm.all_reduce(t)
                        self._is_reduced = True
                        setattr(self, attr, t)

            return func(self, *args, **kwargs)

        return another_wrapper

    wrapper._decorated = True
    return wrapper


def reinit__is_reduced(func: Callable) -> Callable:
    """Helper decorator for distributed configuration.
    See :doc:`metrics` on how to use it.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        func(self, *args, **kwargs)
        self._is_reduced = False

    wrapper._decorated = True
    return wrapper
