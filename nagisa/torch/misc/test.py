import abc
import unittest

import torch
import numpy as np

from nagisa.core.functools import wraps


class _Wrapper(abc.ABC):
    _klass_ = type(None)

    def __init__(self, array):
        assert isinstance(array, self._klass_)
        self._array_ = array

    def __repr__(self):
        return repr(self._array_)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            other = other._array_
        return self._equal_(self._array_, other)

    @abc.abstractclassmethod
    def _equal_(self, first, second):
        pass


class _TensorWrapper(_Wrapper):
    _klass_ = torch.Tensor

    def _equal_(self, t1, t2):
        return (
            isinstance(t2, torch.Tensor) and t1.device == t2.device and t1.shape == t2.shape
            and t1.dtype == t2.dtype and (t1 == t2).all()
        )


class _NdarrayWrapper(_Wrapper):
    _klass_ = np.ndarray

    def _equal_(self, a1, a2):
        return (
            isinstance(a2, np.ndarray) and a1.shape == a2.shape and a1.strides == a2.strides
            and np.array_equal(a1, a2)
        )


def wrap_data(obj):
    if isinstance(obj, (list, tuple, set, frozenset)):
        return type(obj)(wrap_data(x) for x in obj)
    elif isinstance(obj, dict):
        return {k: wrap_data(v) for k, v in obj.items()}
    elif isinstance(obj, torch.Tensor):
        return _TensorWrapper(obj)
    elif isinstance(obj, np.ndarray):
        return _NdarrayWrapper(obj)
    # elif isinstance(obj, Iterable):
    #     return (wrap_data(x) for x in obj)
    else:
        return obj


def _build_method(method_name):

    method = getattr(unittest.TestCase, method_name)

    def _wrapper(self, first, second, *args, **kwargs):
        first, second = map(wrap_data, (first, second))
        return method(self, first, second, *args, **kwargs)

    return wraps(method)(_wrapper)


class TorchTestCase(unittest.TestCase):
    for name in [
            'assertEqual',
            'assertNotEqual',
            'assertSequenceEqual',
            'assertListEqual',
            'assertTupleEqual',
            'assertSetEqual',
            'assertDictEqual',
    ]:
        locals()[name] = _build_method(name)
