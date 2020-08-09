import re
import inspect
from collections import namedtuple
from typing import Union, List, Callable, Optional

__all__ = [
    "match_spec",
]

_ParsedParamSpec = namedtuple("_ParsedParamSpec", ("name", "aliases", "optional", "placeholder"))
Matched = namedtuple('Matched', ('remaining', 'adapter_signature', 'adapter_args'))
ParamsSpecType = List[Union[str, type(Ellipsis)]]

_param_spec_pattern = re.compile(r"^(?P<names>[\w\s\|]+)\s*(?P<optional>\?)?|(?P<placeholder>\*)$")


class _ParamSpecMatcher:
    def __init__(self, spec: ParamsSpecType, f: Callable):
        self.parsed_specs = []
        self.has_remaining = False
        self.spec = spec
        self.params = self._check_static_and_get_params_(f)
        self._parse_specs_(spec)

    @staticmethod
    def _check_static_and_get_params_(f: Callable) -> List[str]:
        sig = inspect.signature(f)
        if not all(p.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ) for p in sig.parameters.values()):
            raise TypeError(f"Expect all arguments of {f} to be positional, got {sig}")
        return list(sig.parameters)

    @staticmethod
    def _parse_param_spec_(spec_item: str) -> Optional[_ParsedParamSpec]:
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

    def _name_generator_(self):
        used_names = set(x.name for x in self.parsed_specs) | set(self.params)
        counter = 0
        used_names = set(used_names).copy()
        while True:
            name = f"_{counter}"
            if name not in used_names:
                used_names.add(name)
                yield name
            counter += 1

    def _parse_specs_(self, spec):
        for i, x in enumerate(spec):
            if x is ...:
                if i != len(spec) - 1:
                    raise RuntimeError("... should be at the last of spec")
                self.has_remaining = True
                continue

            if not isinstance(x, str):
                raise RuntimeError(f"Bad param spec: {x!r}")
            parsed_spec_item = self._parse_param_spec_(x)
            if parsed_spec_item is None:
                raise RuntimeError(f"Bad param spec: {x!r}")
            self.parsed_specs.append(parsed_spec_item)

    def match(self):
        adapter_signature = []
        adapter_args = []
        param_ptr = spec_ptr = 0
        L_spec = len(self.parsed_specs)
        L_param = len(self.params)
        fail_flag = False
        name_generator = self._name_generator_()
        while spec_ptr < L_spec and param_ptr < L_param and not fail_flag:
            param = self.params[param_ptr]
            spec_item = self.parsed_specs[spec_ptr]

            if spec_item.placeholder:
                matched_name = next(name_generator)
            elif param in spec_item.aliases:
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

        while spec_ptr < L_spec and self.parsed_specs[spec_ptr].optional:
            adapter_signature.append(self.parsed_specs[spec_ptr].name)
            spec_ptr += 1

        remaining = self.params[param_ptr:]
        for _ in remaining:
            placeholder_name = next(name_generator)

            adapter_signature.append(placeholder_name)
            adapter_args.append(placeholder_name)

        if len(set(adapter_signature)) != len(adapter_signature):
            fail_flag = True

        fail_flag = fail_flag or spec_ptr != L_spec
        fail_flag = fail_flag or (not self.has_remaining and param_ptr != L_param)

        if fail_flag:
            raise RuntimeError(f"Param list {self.params!r} can not match spec {self.spec!r}")

        return Matched(remaining, adapter_signature, adapter_args)


def match_spec(spec: ParamsSpecType, f: Callable) -> Matched:
    return _ParamSpecMatcher(spec, f).match()
