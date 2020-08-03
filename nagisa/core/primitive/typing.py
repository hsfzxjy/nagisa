import ast

from nagisa.core.primitive.malformed import Malformed

__all__ = [
    "elemT",
    "unwrapT",
    "unnullT",
    "unlistT",
    "is_nullT",
    "is_listT",
    "is_acceptableT",
    "compatible_with",
    "get_default_value",
    "inferT",
    "checkT",
    "strT",
    "cast",
    "str_to_object",
]

_PRIMITIVE_TYPES = [int, float, bool, str]
_ACCEPTED_TYPES = _PRIMITIVE_TYPES.copy()
_ACCEPTED_TYPES.extend([(T, None) for T in _PRIMITIVE_TYPES])
_ACCEPTED_TYPES.extend([[T] for T in _ACCEPTED_TYPES])
_ACCEPTED_TYPES.extend([(T, None) for T in _ACCEPTED_TYPES])

NoneType = type(None)
AnyType = ...


def _is_con_type(x):
    return isinstance(x, (list, tuple))


def elemT(T):
    while _is_con_type(T):
        T = unwrapT(T)

    return T


def unwrapT(T):
    return T[0] if _is_con_type(T) else T


def unnullT(T):
    return unwrapT(T) if is_nullT(T) else T


def unlistT(T):
    return unwrapT(T) if is_listT(T) else T


def is_nullT(T) -> bool:
    return isinstance(T, tuple)


def is_listT(T) -> bool:
    return isinstance(T, list)


def is_acceptableT(T, *, raise_exc=False) -> bool:
    result = T in _ACCEPTED_TYPES
    if not result and raise_exc:
        raise TypeError(f'Unsupported type {T!r}')
    return result


def compatible_with(T1, T2) -> bool:
    """
    Values of T2 covers values of T1
    """
    if T2 is AnyType:
        return True

    if T1 is NoneType:
        return T2 is NoneType or is_nullT(T2)

    if T1 is Malformed or T2 is Malformed:
        return False

    if T1 == T2:
        return True

    if T1 is int and T2 is float:
        return True

    if is_nullT(T2):
        return compatible_with(T1, unwrapT(T2))

    if is_listT(T1) and is_listT(T2):
        return T1 == [] or compatible_with(unwrapT(T1), unwrapT(T2))

    return False


def topper(T1, T2):
    if T1 is Malformed or T2 is Malformed:
        return Malformed
    elif not (_is_con_type(T1) or _is_con_type(T2)):
        if T1 is T2:
            ret = T1
        elif {T1, T2} == {int, float}:
            ret = float
        elif T1 == T2 == AnyType:
            ret = AnyType
        elif T1 is AnyType:
            ret = T2
        elif T2 is AnyType:
            ret = T1
        else:
            ret = Malformed

        return ret if ret in {AnyType, NoneType, *_PRIMITIVE_TYPES} else Malformed
    elif T1 is NoneType or T2 is NoneType:
        if T2 is NoneType:
            T1, T2 = T2, T1
        return T2 if is_nullT(T2) else (T2, None)
    elif is_nullT(T1) or is_nullT(T2):
        inner_T1, inner_T2 = map(unnullT, (T1, T2))
        topper_inner = topper(inner_T1, inner_T2)
        return (topper_inner, None) if topper_inner is not Malformed else Malformed
    elif is_listT(T1) and is_listT(T2):
        if T1 == T2 == []:
            return []
        elif T1 == []:
            return T2
        elif T2 == []:
            return T1
        topperelemT = topper(unlistT(T1), unlistT(T2))
        return [topperelemT] if topperelemT is not Malformed else Malformed
    else:
        return Malformed


def get_default_value(T):
    if is_nullT(T):
        return None
    elif is_listT(T):
        return []
    else:
        return T()


def inferT(value, *, allow_empty_list=False, expect_non_list=False):
    type_ = type(value)
    if type_ in (list, tuple):
        if expect_non_list:
            return AnyType

        if len(value) == 0:
            if not allow_empty_list:
                raise TypeError(f"Cannot infer type for empty container {value!r}.")
            return []

        base_type = AnyType
        for x in value:
            type_of_x = inferT(x, expect_non_list=True)
            base_type = topper(base_type, type_of_x)

        if base_type in {AnyType, NoneType, Malformed}:
            raise TypeError(f'Cannot infer type for {value!r}, got element type {base_type!r}')

        return [base_type]

    return type_


def checkT(value, T, *, check=True) -> bool:
    if check:
        assert is_acceptableT(T)

    return compatible_with(inferT(value, allow_empty_list=True), T)


def strT(T, *, check=True) -> str:
    if check:
        assert is_acceptableT(T)

    if is_nullT(T):
        return strT(unwrapT(T), check=False) + '?'
    elif is_listT(T):
        return '[' + strT(unwrapT(T), check=False) + ']'
    else:
        return T.__name__


def cast(value, T, *, check=True, raise_exc=True):
    if check:
        assert is_acceptableT(T)

    if value is Malformed:
        return Malformed

    if not checkT(value, T, check=False):
        if isinstance(value, str):
            obj = str_to_object(value)
            ret = cast(obj, T, check=False, raise_exc=False)
            if ret is Malformed and unnullT(T) is str:
                ret = value
        else:
            ret = Malformed

        if raise_exc and ret is Malformed:
            raise TypeError(f"Cannot cast {value!r} into {strT(T)}")

        return ret

    if T is AnyType:
        return value

    if value is None:
        return value

    if is_nullT(T):
        T = unwrapT(T)

    if is_listT(T):
        base_type = unlistT(T)
        return [cast(x, base_type, check=False) for x in value]

    return T(value)


def str_to_object(string, *, default=Malformed):
    try:
        return ast.literal_eval(string)
    except (SyntaxError, ValueError):
        return default
