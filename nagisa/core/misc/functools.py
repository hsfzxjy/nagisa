import re
import types
import inspect
import textwrap
import functools
import itertools
from collections import namedtuple
from typing import Union, List, Tuple, Dict, Callable, Optional, Any, Set

from nagisa.core.misc import accessor
from nagisa.core.misc.naming import isidentifier, isaccessor

__all__ = [
    "match_params_spec",
    "function_annotator",
    "make_adapter",
    "adapt_params_spec",
    "make_function",
]


def _check_static_and_get_params(f: Callable) -> List[str]:
    params = inspect.signature(f).parameters
    if not all(p.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ) for p in params.values()):
        raise TypeError  # TODO detailed info
    return list(params)


_ParsedParamSpec = namedtuple(
    "_ParsedParamSpec", ("name", "aliases", "optional", "placeholder")
)
_ParsedAdapterMapping = namedtuple("_ParsedAdapterMapping", ("args", "kwargs"))

ParamsSpecType = List[Union[str, type(Ellipsis)]]
AdapterMappingType = Union[List[str],
                           Dict[str, str],
                           Tuple[List[str], Dict[str, str]],
                           ]

_param_spec_regexp = re.compile(
    r"^(?P<names>[\w\s\|]+)\s*(?P<optional>\?)?|(?P<placeholder>\*)$"
)


def _parse_param_spec(spec_item: str) -> Optional[_ParsedParamSpec]:
    matched = _param_spec_regexp.match(spec_item)

    if matched is None:
        return None

    if matched.group("placeholder") is not None:
        return _ParsedParamSpec("", frozenset(), False, True)

    names = [x.strip() for x in re.split(r"\s*\|\s*", matched.group("names"))]
    if not all(map(str.isidentifier, names)):
        return None

    return _ParsedParamSpec(
        name=names[0],
        aliases=frozenset(names),
        optional=matched.group("optional") is not None,
        placeholder=False,
    )


def match_params_spec(
    spec: ParamsSpecType,
    f: Callable,
    simple: bool = True
) -> Union[List[str], Tuple[List[str], List[str], _ParsedAdapterMapping]]:
    params = _check_static_and_get_params(f)

    parsed_specs = []
    has_remaining = False
    for i, x in enumerate(spec):
        if x is ...:
            assert i == len(spec) - 1
            has_remaining = True
            continue

        assert isinstance(x, str)
        parsed_spec_item = _parse_param_spec(x)
        assert parsed_spec_item is not None, f"Bad param spec: {x!r}"
        parsed_specs.append(parsed_spec_item)

    adapter_params = []
    mapping = []
    param_ptr = spec_ptr = 0
    L_spec = len(parsed_specs)
    L_param = len(params)
    placeholder_name = "_"
    used_names = set(x.name for x in parsed_specs) | set(params)
    fail_flag = False
    while spec_ptr < L_spec and param_ptr < L_param and not fail_flag:
        param = params[param_ptr]
        spec_item = parsed_specs[spec_ptr]

        if spec_item.placeholder:
            while placeholder_name in used_names:
                placeholder_name += "_"

            used_names.add(placeholder_name)
            matched_name = placeholder_name
        else:
            if param in spec_item.aliases:
                matched_name = spec_item.name
            elif spec_item.optional:
                spec_ptr += 1
                adapter_params.append(spec_item.name)
                continue
            else:
                fail_flag = True
                continue

        adapter_params.append(matched_name)
        mapping.append(matched_name)
        param_ptr += 1
        spec_ptr += 1

    while spec_ptr < L_spec and parsed_specs[spec_ptr].optional:
        adapter_params.append(parsed_specs[spec_ptr].name)
        spec_ptr += 1

    remaining = params[param_ptr:]
    for name in remaining:
        while placeholder_name in used_names:
            placeholder_name += "_"
        used_names.add(placeholder_name)

        adapter_params.append(placeholder_name)
        mapping.append(placeholder_name)

    if len(set(adapter_params)) != len(adapter_params):
        fail_flag = True

    fail_flag = fail_flag or spec_ptr != L_spec
    fail_flag = fail_flag or (not has_remaining and param_ptr != L_param)

    if fail_flag:
        raise RuntimeError(
            f"Param list {params!r} can not match params spec {spec!r}."
        )

    if simple:
        return remaining
    else:
        return (
            remaining,
            adapter_params,
            _ParsedAdapterMapping(args=mapping, kwargs={}),
        )


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
            '{!r}: {}'.format(k, _accessor_fragment(v, used_names))
            for k, v in accessor.items()
        )
        return '{{{}}}'.format(', '.join(elements))
    else:
        raise RuntimeError(f'Unknown accessor {accessor!r}')


def _arg_fragment(
    accessor: Any, used_names: Set[str], keyword: Optional[str] = None
) -> str:
    result = "" if keyword is None else f"{keyword}="
    return result + _accessor_fragment(accessor, used_names)


def _call_func_fragment(mapping: _ParsedAdapterMapping) -> Set[str]:
    used_names = set()

    return ", ".join(
        itertools.chain(
            (_arg_fragment(x, used_names) for x in mapping.args),
            (
                _arg_fragment(x, used_names, k)
                for k, x in mapping.kwargs.items()
            ),
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


def _parse_adapter_mapping_spec(
    mapping: AdapterMappingType,
) -> _ParsedAdapterMapping:
    args = []
    kwargs = {}
    if isinstance(mapping, _ParsedAdapterMapping):
        return mapping
    elif isinstance(mapping, list):
        args = mapping
    elif isinstance(mapping, dict):
        kwargs = mapping
    elif isinstance(mapping, tuple):
        assert len(mapping) == 2
        args, kwargs = mapping
        assert isinstance(args, list)
        assert isinstance(kwargs, dict)
    else:
        raise AssertionError(
            f"Unknown type {type(mapping)!r} for adpater mapping spec."
        )

    for accessor in itertools.chain(args, kwargs.values()):
        if not _check_accessor(accessor):
            raise AssertionError(f"{accessor!r} is not a valid accessor.")

    for name in kwargs.keys():
        if not isidentifier(name):
            raise AssertionError(f"{name!r} is not a valid identifier.")

    return _ParsedAdapterMapping(args=args, kwargs=kwargs)


def make_adapter(
    adapter_params: List[str],
    mapping: AdapterMappingType,
    f: Optional[Callable] = None,
) -> Callable:
    def _decorator(f: Callable) -> Callable:
        nonlocal mapping
        assert all(map(isidentifier, adapter_params))
        mapping = _parse_adapter_mapping_spec(mapping)

        func_name = f.__name__
        if not isidentifier(func_name):
            func_name = "F"
        arg_list_str, used_names = _call_func_fragment(mapping)
        define_input_str = _define_input_fragment(used_names)

        new_f = make_function(
            func_name,
            f"""
            def F({', '.join(adapter_params)}):
                {define_input_str}
                return ___FUNC___({arg_list_str})
            """,
            dict(dict=dict, ___FUNC___=f, ___ACCESSOR_GET___=accessor.get),
        )
        functools.update_wrapper(new_f, f)

        new_f.__is_adapter__ = True
        return new_f

    return _decorator if f is None else _decorator(f)


def adapt_params_spec(
    spec: ParamsSpecType,
    f: Optional[Callable] = None,
    preserve_meta: bool = False
) -> Callable:
    def _decorator(f: Callable) -> Callable:
        remaining, adapter_params, mapping = match_params_spec(
            spec, f, simple=False
        )
        new_f = make_adapter(adapter_params, mapping, f)

        if preserve_meta:
            new_f.__remaining__ = remaining
            new_f.__adapter_mapping_spec__ = mapping

        return new_f

    return _decorator if f is None else _decorator(f)


def function_annotator(f, spec, slot_name, init_fn, annotate_fn):
    def _decorator(func):
        nonlocal f
        value = getattr(func, slot_name, init_fn())
        if f is not None:
            f = adapt_params_spec(spec, f)
            value = annotate_fn(value, f)
        setattr(func, slot_name, value)
        return func

    return _decorator


def make_function(name: str, body: str, globals: dict = None) -> Callable:
    body = textwrap.dedent(body)
    func_code = compile(body, "<string>", "exec")
    if globals is None:
        globals = {}
    return types.FunctionType(func_code.co_consts[0], globals, name)
