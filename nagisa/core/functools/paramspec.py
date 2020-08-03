import re
import types
import inspect
import textwrap
import functools
import itertools
from collections import namedtuple
from typing import Union, List, Tuple, Dict, Callable, Optional, Any, Set

from nagisa.core.misc.naming import isidentifier, isaccessor

__all__ = [
    "match_spec",
]


def _check_static_and_get_params(f: Callable) -> List[str]:
    params = inspect.signature(f).parameters
    if not all(p.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ) for p in params.values()):
        raise TypeError  # TODO detailed info
    return list(params)


_ParsedParamSpec = namedtuple("_ParsedParamSpec", ("name", "aliases", "optional", "placeholder"))
Matched = namedtuple('Matched', ('remaining', 'adapter_signature', 'adapter_args'))
ParamsSpecType = List[Union[str, type(Ellipsis)]]

_param_spec_pattern = re.compile(r"^(?P<names>[\w\s\|]+)\s*(?P<optional>\?)?|(?P<placeholder>\*)$")


def _parse_param_spec(spec_item: str) -> Optional[_ParsedParamSpec]:
    matched = _param_spec_pattern.match(spec_item)

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


def _placeholder_list():
    counter = 0
    while True:
        yield f"_{counter}"
        counter += 1


def match_spec(spec: ParamsSpecType, f: Callable) -> Matched:
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

    adapter_signature = []
    adapter_args = []
    param_ptr = spec_ptr = 0
    L_spec = len(parsed_specs)
    L_param = len(params)
    placeholder_generator = _placeholder_list()
    placeholder_name = next(placeholder_generator)
    used_names = set(x.name for x in parsed_specs) | set(params)
    fail_flag = False
    while spec_ptr < L_spec and param_ptr < L_param and not fail_flag:
        param = params[param_ptr]
        spec_item = parsed_specs[spec_ptr]

        if spec_item.placeholder:
            while placeholder_name in used_names:
                placeholder_name = next(placeholder_generator)

            used_names.add(placeholder_name)
            matched_name = placeholder_name
        else:
            if param in spec_item.aliases:
                matched_name = spec_item.name
            elif spec_item.optional:
                spec_ptr += 1
                adapter_signature.append(spec_item.name)
                continue
            else:
                fail_flag = True
                continue

        adapter_signature.append(matched_name)
        adapter_args.append(matched_name)
        param_ptr += 1
        spec_ptr += 1

    while spec_ptr < L_spec and parsed_specs[spec_ptr].optional:
        adapter_signature.append(parsed_specs[spec_ptr].name)
        spec_ptr += 1

    remaining = params[param_ptr:]
    for name in remaining:
        while placeholder_name in used_names:
            placeholder_name = next(placeholder_generator)
        used_names.add(placeholder_name)

        adapter_signature.append(placeholder_name)
        adapter_args.append(placeholder_name)

    if len(set(adapter_signature)) != len(adapter_signature):
        fail_flag = True

    fail_flag = fail_flag or spec_ptr != L_spec
    fail_flag = fail_flag or (not has_remaining and param_ptr != L_param)

    if fail_flag:
        raise RuntimeError(f"Param list {params!r} can not match spec {spec!r}")

    return Matched(remaining, adapter_signature, adapter_args)
