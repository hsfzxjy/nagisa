import functools
import itertools
import importlib
from collections import namedtuple
from typing import List, Dict, Callable, Optional, Any, Set

from nagisa.core.misc.naming import isidentifier, isaccessor

from .paramspec import match_spec
from .hof import make_function, decorative

__all__ = [
    "adapt",
    "adapt_spec",
    "make_annotator",
]

_ParsedAdapterMapping = namedtuple("_ParsedAdapterMapping", ("args", "kwargs"))


def _define_input_fragment(used_names: Set[str]) -> str:
    if not used_names:
        return ""

    return f"""___INPUT___ = dict({', '.join(x + '=' + x for x in used_names)})"""


def _accessor_fragment(accessor: Any, used_names: Set[str]) -> str:
    T = type(accessor)
    if T is str:
        if "." not in accessor:
            used_names.add(accessor)
            return accessor
        else:
            used_names.add(accessor.partition('.')[0])
            return f"___ACCESSOR_GET___(___INPUT___, {accessor!r})"
    elif T in (tuple, list):
        elements = (_accessor_fragment(x, used_names) for x in accessor)
        return {
            tuple: '({},)',
            list: '[{}]',
        }[T].format(', '.join(elements))
    elif T is dict:
        elements = (
            '{!r}: {}'.format(k, _accessor_fragment(v, used_names)) for k, v in accessor.items()
        )
        return '{{{}}}'.format(', '.join(elements))
    else:
        raise RuntimeError(f'Unknown accessor {accessor!r}')


def _arg_fragment(accessor: Any, used_names: Set[str], keyword: Optional[str] = None) -> str:
    result = "" if keyword is None else f"{keyword}="
    return result + _accessor_fragment(accessor, used_names)


def _call_func_fragment(mapping: _ParsedAdapterMapping) -> Set[str]:
    used_names = set()

    return ", ".join(
        itertools.chain(
            (_arg_fragment(x, used_names) for x in mapping.args),
            (_arg_fragment(x, used_names, k) for k, x in mapping.kwargs.items()),
        )
    ), used_names


def _check_accessor(accessor: Any) -> bool:
    if isinstance(accessor, str):
        return isaccessor(accessor)
    if isinstance(accessor, (list, tuple)):
        return all(map(_check_accessor, accessor))
    if isinstance(accessor, dict):
        return all(map(_check_accessor, accessor.values()))
    return False


def _parse_adapter_mapping(args: Optional[List], kwargs: Optional[Dict]) -> _ParsedAdapterMapping:
    if args is None:
        args = []
    else:
        assert isinstance(args, list)

    if kwargs is None:
        kwargs = {}
    else:
        assert isinstance(kwargs, dict)

    for accessor in itertools.chain(args, kwargs.values()):
        if not _check_accessor(accessor):
            raise AssertionError(f"{accessor!r} is not a valid accessor.")

    for name in kwargs.keys():
        if not isidentifier(name):
            raise AssertionError(f"{name!r} is not a valid identifier.")

    return _ParsedAdapterMapping(args=args, kwargs=kwargs)


@decorative(name='f')
def adapt(
    signature: List[str],
    f: Optional[Callable] = None,
    *,
    args: Optional[List] = None,
    kwargs: Optional[Dict] = None,
) -> Callable:
    assert callable(f)
    assert all(map(isidentifier, signature))
    mapping = _parse_adapter_mapping(args, kwargs)

    func_name = f.__name__
    arg_list_str, used_names = _call_func_fragment(mapping)
    define_input_str = _define_input_fragment(used_names)

    new_f = make_function(
        func_name,
        f"""
        def F({', '.join(signature)}):
            {define_input_str}
            return ___FUNC___({arg_list_str})
        """,
        globals=dict(
            dict=dict,
            ___FUNC___=f,
            ___ACCESSOR_GET___=importlib.import_module('nagisa.core.misc.accessor').get,
        ),
    )
    functools.update_wrapper(new_f, f)

    new_f.__is_adapter__ = True
    return new_f


def make_annotator(
    f: Callable,
    spec,
    slot_name: str,
    init_fn: Callable,
    annotate_fn: Callable,
    *,
    inplace: bool = False
) -> Callable:
    def _decorator(host_f):
        nonlocal f
        value = getattr(host_f, slot_name, None)
        if value is None:
            value = init_fn()
            setattr(host_f, slot_name, value)
        if f is not None:
            f = adapt_spec(spec, f)
            if inplace:
                value = annotate_fn(value, f)
                setattr(host_f, slot_name, value)
            else:
                annotate_fn(value, f)
        return host_f

    _decorator.__init_fn__ = init_fn

    return _decorator


@decorative(name='f')
def adapt_spec(spec, f: Optional[Callable] = None, preserve_meta: bool = False) -> Callable:
    remaining, signature, args = match_spec(spec, f)
    new_f = adapt(signature, f, args=args)

    if preserve_meta:
        new_f.__remaining__ = remaining
        new_f.__adapter_mapping_spec__ = args

    return new_f
