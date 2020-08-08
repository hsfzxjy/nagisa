import enum
import torch
import numbers

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


def to_tensor(x) -> torch.Tensor:
    if isinstance(x, numbers.Number):
        x = torch.tensor(x)
    elif _SUPPORT_NUMPY and isinstance(x, numpy.ndarray):
        x = torch.from_numpy(x)
    elif isinstance(x, torch.Tensor):
        x = detach(x)
    else:
        _not_implemented(f"Unknown type {type(x)!r}")

    return x
