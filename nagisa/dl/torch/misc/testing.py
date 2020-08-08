import os
import abc
import unittest

import numpy as np
import torch
import torch.distributed as torch_dist
import torch.multiprocessing as torch_mp

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

    @abc.abstractmethod
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


def _wrap_data(obj):
    if isinstance(obj, (list, tuple, set, frozenset)):
        return type(obj)(_wrap_data(x) for x in obj)
    elif isinstance(obj, dict):
        return {k: _wrap_data(v) for k, v in obj.items()}
    elif isinstance(obj, torch.Tensor):
        return _TensorWrapper(obj)
    elif isinstance(obj, np.ndarray):
        return _NdarrayWrapper(obj)
    else:
        return obj


def _build_method(method_name):

    method = getattr(unittest.TestCase, method_name)

    def _wrapper(self, first, second, *args, **kwargs):
        first, second = map(_wrap_data, (first, second))
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


def init_process(rank, size, backend, Q, done_events, exit_event, main, args):
    os.environ['MASTER_ADDR'] = '127.0.0.1'
    os.environ['MASTER_PORT'] = '29500'
    torch_dist.init_process_group(backend, rank=rank, world_size=size)
    main(*args, Q, rank, size)
    done_events[rank].set()
    exit_event.wait()


def mp_call(main, *, size=4, backend='gloo', args=()):
    mp_ctx = torch_mp.get_context('spawn')
    Q = mp_ctx.SimpleQueue()

    done_events = [mp_ctx.Event() for _ in range(size)]
    exit_event = mp_ctx.Event()

    processes = torch_mp.spawn(
        init_process,
        args=(size, backend, Q, done_events, exit_event, main, args),
        nprocs=size,
        join=False
    )

    for event in done_events:
        event.wait()

    result = []
    while not Q.empty():
        result.append(Q.get())

    exit_event.set()
    processes.join()

    return result
