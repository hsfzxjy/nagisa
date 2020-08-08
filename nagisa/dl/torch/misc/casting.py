# pylint: disable=not-callable
import numbers

import torch

try:
    import numpy

    _SUPPORT_NUMPY = True
except ImportError:
    _SUPPORT_NUMPY = False


def _not_implemented(msg=None):
    raise NotImplementedError(msg)


def detach(x: torch.Tensor):
    return x.cpu().clone().detach_()


def as_(x, target: torch.Tensor) -> torch.Tensor:
    if isinstance(x, numbers.Number):
        x = target.new_tensor(x)
    elif _SUPPORT_NUMPY and isinstance(x, numpy.ndarray):
        x = target.new_tensor(x)
    elif isinstance(x, torch.Tensor):
        x = detach(x).type_as(target)
    else:
        _not_implemented(f"Unknown type {type(x)!r}")

    return x


def to_tensor(x, *, detrans=False) -> torch.Tensor:
    if isinstance(x, numbers.Number):
        transform = type(x)
        x = torch.tensor(x)
    elif _SUPPORT_NUMPY and isinstance(x, numpy.ndarray):
        dtype = x.dtype
        transform = lambda x: numpy.array(x, dtype=dtype)
        x = torch.from_numpy(x)
    elif isinstance(x, torch.Tensor):
        dtype, device = x.dtype, x.device
        transform = lambda x: x.type_as(dtype).to(device)
        x = detach(x)
    else:
        _not_implemented(f"Unknown type {type(x)!r}")

    return (x, transform) if detrans else x
