import enum
import torch
import numbers

try:
    import numpy

    _SUPPORT_NUMPY = True
except ImportError:
    _SUPPORT_NUMPY = False


class NumericType(enum.Enum):

    SCALAR = enum.auto()
    NUMPY = enum.auto()
    TORCH = enum.auto()
    UNKNOWN = enum.auto()


def _not_implemented(msg=None):
    raise NotImplementedError(msg)


def as_float(x):
    T = type_of(x)
    if T == NumericType.SCALAR:
        return float(x)
    elif T == NumericType.NUMPY:
        return x.astype(numpy.float32)
    elif T == NumericType.TORCH:
        return x.float()
    else:
        _not_implemented()


def axis_kw(T: NumericType) -> str:
    return {NumericType.NUMPY: "axis", NumericType.TORCH: "dim"}.get(T) or _not_implemented()


def detach(x):
    T = type_of(x)
    if T == NumericType.SCALAR:
        return x
    elif T == NumericType.NUMPY:
        return x.copy()
    elif T == NumericType.TORCH:
        return x.cpu().clone().detach_()
    else:
        _not_implemented()


def type_of(x, raise_exc=False) -> NumericType:
    if isinstance(x, numbers.Number):
        return NumericType.SCALAR
    elif _SUPPORT_NUMPY and isinstance(x, numpy.ndarray):
        return NumericType.NUMPY
    elif isinstance(x, torch.Tensor):
        return NumericType.TORCH
    else:
        if raise_exc:
            _not_implemented()
        return NumericType.UNKNOWN


def zeros_like(x):

    return {
        NumericType.SCALAR: lambda: type(x)(0),
        NumericType.NUMPY: lambda: numpy.zeros_like(x),
        NumericType.TORCH: lambda: torch.zeros_like(x),
        NumericType.UNKNOWN: lambda: _not_implemented(),
    }[type_of(x)]()


def cast_as(x, target):

    x_type, target_type = map(type_of, (x, target))

    if NumericType.UNKNOWN in (x_type, target_type):
        _not_implemented()

    if x_type == NumericType.TORCH:
        x = x.cpu().detach()

    return {
        NumericType.SCALAR: type(target),
        NumericType.NUMPY: lambda x: numpy.array(x, dtype=target.dtype),
        NumericType.TORCH: lambda x: target.new_tensor(x),
    }[target_type](
        x
    )


def shape_of(x):

    return {
        NumericType.SCALAR: tuple,
        NumericType.NUMPY: lambda: x.shape,
        NumericType.TORCH: lambda: tuple(x.shape),
        NumericType.UNKNOWN: _not_implemented,
    }[type_of(x)]()


def same_shape(x, y, raise_exc=False):

    x_shape, y_shape = map(shape_of, (x, y))
    result = x_shape == y_shape

    if not result and raise_exc:
        raise ValueError(f"Shapes not matched: {x_shape} != {y_shape}")

    return result
