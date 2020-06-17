import typing
try:
    # python >= 3.7
    _generic_alias_base = typing._GenericAlias
except AttributeError:
    # python <= 3.6
    _generic_alias_base = typing.GenericMeta

from typing import List, Tuple, Any
from collections import namedtuple

__all__ = [
    'is_acceptable_type', 'compatible_with', 'get_default_value', 'infer_type', 
    'check_type', 'stringify_type', 'regularize_type', 'cast'
]

_PRIMITIVE_TYPES = (int, float, bool, str)
_ACCEPTED_TYPES = frozenset([
    *_PRIMITIVE_TYPES,
    *(List[x] for x in _PRIMITIVE_TYPES),
])

def _base_type(T):
    if _is_list(T):
        return T.__args__[0]
    else:
        return T

def _is_list(T) -> bool:
    return T in (List, list, Tuple, tuple) or (
        isinstance(T, _generic_alias_base) and 
        T.__origin__ in (List, list, Tuple, tuple)
    )

def is_acceptable_type(T):
    try:
        T = regularize_type(T)
    except AssertionError: # TODO
        pass
    
    try:
        return T in _ACCEPTED_TYPES
    except TypeError:
        # `T` may be unhashable
        return False

def compatible_with(T1, T2) -> bool:

    if T1 is T2:
        return True

    if T1 is int and T2 is float:
        return True

    if _is_list(T1) and _is_list(T2):
        return compatible_with(_base_type(T1), _base_type(T2))

    return False

def get_default_value(T):
    return [] if _is_list(T) else T()

def infer_type(value, allow_empty_list=False):
    type_ = type(value)
    if type_ in (list, tuple):
        if len(value) == 0:
            if not allow_empty_list:
                raise TypeError('Cannot infer type for empty container {!r}.'.format(value))
            return List

        base_type = infer_type(value[0])
        for i, x in enumerate(value[1:], start=1):
            if not compatible_with(infer_type(x), base_type):
                raise TypeError(
                    'Cannot infer type for container object {!r}, '
                    'since the {}-th element {!r} has different type as previous.'.format(value, i, x))

        return List[base_type]

    return type_

def check_type(value, T) -> bool:
    if _is_list(T) and _is_list(infer_type(value, allow_empty_list=True)) and not value:
        return True

    return compatible_with(infer_type(value, allow_empty_list=True), T)

def stringify_type(T) -> str:
    if not _is_list(T):
        return T.__name__

    return '[{}]'.format(stringify_type(_base_type(T)))

def regularize_type(T):
    if isinstance(T, list):
        assert len(T) == 1, 'Bad type {!r}.'.format(T)
        return List[T[0]]

    return T

def cast(value, T):
    if not check_type(value, T):
        raise TypeError("Cannot cast {!r} into {!r}.".format(value, T))

    if _is_list(T):
        if not value:
            return []
        base_type = _base_type(T)
        return [base_type(x) for x in value]

    return T(value)
