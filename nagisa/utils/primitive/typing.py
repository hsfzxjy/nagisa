import sys
import ast
import typing
from typing import List, Tuple, Optional

if sys.version_info >= (3, 7, 0):
    _generic_alias_base = _optional_base = typing._GenericAlias
else:
    _generic_alias_base = typing.GenericMeta
    _optional_base = typing._Union

from collections import namedtuple
from nagisa.utils.primitive.malformed import Malformed

__all__ = [
    "is_acceptable_type",
    "compatible_with",
    "get_default_value",
    "infer_type",
    "check_type",
    "stringify_type",
    "regularize_type",
    "cast",
    "str_to_object",
]

_PRIMITIVE_TYPES = (int, float, bool, str)
_ACCEPTED_TYPES = frozenset([*_PRIMITIVE_TYPES, *(List[T] for T in _PRIMITIVE_TYPES),])
_ACCEPTED_TYPES = _ACCEPTED_TYPES | frozenset([Optional[T] for T in _ACCEPTED_TYPES])

NoneType = type(None)


def _elem(T):
    while isinstance(T, (_generic_alias_base, _optional_base)):
        T = _unwrap(T)
    return T


def _unwrap(T):
    if isinstance(T, (_generic_alias_base, _optional_base)):
        L = len(T.__args__)
        if L == 1:
            return T.__args__[0]
        elif L == 2:
            return T.__args__[0 if T.__args__[1] is NoneType else 1]
    return T


def _is_nullable(T) -> bool:

    return (
        isinstance(T, (_optional_base))
        and T.__origin__ is typing.Union
        and len(T.__args__) == 2
        and type(None) in T.__args__
    )


def _is_list(T) -> bool:
    return (
        T in (List, list, Tuple, tuple)
        or (_is_nullable(T) and _is_list(_unwrap(T)))
        or (
            isinstance(T, _generic_alias_base)
            and T.__origin__ in (List, list, Tuple, tuple)
        )
    )


def is_acceptable_type(T):
    try:
        T = regularize_type(T)
    except AssertionError:  # TODO
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

    if _is_nullable(T2):
        return T1 is NoneType or compatible_with(T1, _unwrap(T2))

    if _is_list(T1) and _is_list(T2):
        return compatible_with(_elem(T1), _elem(T2))

    return False


def get_default_value(T):
    if _is_nullable(T):
        return None
    elif _is_list(T):
        return []
    else:
        return T()


def infer_type(value, allow_empty_list=False):
    type_ = type(value)
    if type_ in (list, tuple):
        if len(value) == 0:
            if not allow_empty_list:
                raise TypeError(
                    "Cannot infer type for empty container {!r}.".format(value)
                )
            return List

        base_type = infer_type(value[0])
        for i, x in enumerate(value[1:], start=1):
            if not compatible_with(infer_type(x), base_type):
                raise TypeError(
                    "Cannot infer type for container object {!r}, "
                    "since the {}-th element {!r} has different type as previous.".format(
                        value, i, x
                    )
                )

        return List[base_type]

    return type_


def check_type(value, T) -> bool:
    if _is_nullable(T) and value is None:
        return True
    if _is_list(T) and (value == [] or value == ()):
        return True

    return compatible_with(infer_type(value, allow_empty_list=True), T)


def stringify_type(T) -> str:

    suffix = ""
    if _is_nullable(T):
        T = _unwrap(T)
        suffix = "?"

    if not _is_list(T):
        return T.__name__ + suffix

    return "[{}]".format(stringify_type(_elem(T))) + suffix


def regularize_type(T):
    if isinstance(T, list) and len(T) == 1 and T[0] in _ACCEPTED_TYPES:
        return List[T[0]]

    return T


def cast(value, T):
    if value is Malformed:
        return value

    if not check_type(value, T):
        raise TypeError("Cannot cast {!r} into {!r}.".format(value, T))

    if value is None:
        return value

    if _is_nullable(T):
        T = _unwrap(T)

    if _is_list(T):
        if not value:
            return []
        base_type = _elem(T)
        return [base_type(x) for x in value]

    return T(value)


def str_to_object(string, *, default=Malformed):
    try:
        return ast.literal_eval(string)
    except (SyntaxError, ValueError):
        return default
