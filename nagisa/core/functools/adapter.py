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

_ParsedMapping = namedtuple("_ParsedMapping", ("args", "kwargs"))


class _Adapter:
    def __init__(self, signature, f, args, kwargs):
        assert callable(f)
        assert all(map(isidentifier, signature))

        self.signature = signature
        self.f = f
        self.used_names = set()
        self.mapping = self._parse_mapping_(args, kwargs)

    def _check_accessor_(self, accessor: Any) -> bool:
        if isinstance(accessor, str):
            if "." not in accessor:
                self.used_names.add(accessor)
            else:
                self.used_names.add(accessor.partition('.')[0])
            return isaccessor(accessor)
        if isinstance(accessor, (list, tuple)):
            return all(map(self._check_accessor_, accessor))
        if isinstance(accessor, dict):
            return all(map(self._check_accessor_, accessor.values()))
        return False

    def _parse_mapping_(self, args: Optional[List], kwargs: Optional[Dict]) -> _ParsedMapping:
        if args is None:
            args = []
        else:
            assert isinstance(args, list)

        if kwargs is None:
            kwargs = {}
        else:
            assert isinstance(kwargs, dict)

        for accessor in itertools.chain(args, kwargs.values()):
            if not self._check_accessor_(accessor):
                raise AssertionError(f"{accessor!r} is not a valid accessor")

        for name in kwargs.keys():
            if not isidentifier(name):
                raise AssertionError(f"{name!r} is not a valid identifier")

        return _ParsedMapping(args=args, kwargs=kwargs)

    def _snippet_accessor_(self, accessor: Any) -> str:
        T = type(accessor)
        if T is str:
            if "." not in accessor:
                return accessor
            else:
                return f"___ACCESSOR_GET___(___INPUT___, {accessor!r})"
        elif T in (tuple, list):
            elements = (self._snippet_accessor_(x) for x in accessor)
            return {
                tuple: '({},)',
                list: '[{}]',
            }[T].format(', '.join(elements))
        elif T is dict:
            elements = (
                '{!r}: {}'.format(k, self._snippet_accessor_(v)) for k, v in accessor.items()
            )
            return '{{{}}}'.format(', '.join(elements))
        else:
            raise RuntimeError(f'Unknown accessor {accessor!r}')

    def _snippet_arg_(self, accessor: Any, keyword: Optional[str] = None) -> str:
        result = "" if keyword is None else f"{keyword}="
        return result + self._snippet_accessor_(accessor)

    def _snippet_call_func_(self) -> Set[str]:
        mapping = self.mapping
        return ", ".join(
            itertools.chain(
                (self._snippet_arg_(x) for x in mapping.args),
                (self._snippet_arg_(x, k) for k, x in mapping.kwargs.items()),
            )
        )

    def _snippet_define_input_(self) -> str:
        if not self.used_names:
            return ""

        return f"""___INPUT___ = dict({', '.join(x + '=' + x for x in self.used_names)})"""

    def _snippet_func_body_(self):
        str_arg_list = self._snippet_call_func_()
        str_define_input = self._snippet_define_input_()
        return f"""
        def F({', '.join(self.signature)}):
            {str_define_input}
            return ___FUNC___({str_arg_list})
        """

    def make(self):
        func_name = self.f.__name__
        new_f = make_function(
            func_name,
            self._snippet_func_body_(),
            globals=dict(
                dict=dict,
                ___FUNC___=self.f,
                ___ACCESSOR_GET___=importlib.import_module('nagisa.core.misc.accessor').get,
            ),
        )
        functools.update_wrapper(new_f, self.f)

        new_f.__is_adapter__ = True
        return new_f


@decorative(name='f')
def adapt(
    signature: List[str],
    f: Optional[Callable] = None,
    *,
    args: Optional[List] = None,
    kwargs: Optional[Dict] = None,
) -> Callable:
    return _Adapter(signature, f, args, kwargs).make()


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
def adapt_spec(spec, f: Optional[Callable] = None, keep_meta: bool = False) -> Callable:
    remaining, signature, args = match_spec(spec, f)
    new_f = adapt(signature, f, args=args)

    if keep_meta:
        new_f.__remaining__ = remaining
        new_f.__adapter_mapping_spec__ = args

    return new_f
