import types
import inspect
import textwrap
import functools
from typing import Optional, Callable

__all__ = [
    'make_function',
    'emulate',
    'wraps',
    'decorative',
]


# pylint: disable=redefined-builtin
def make_function(
    name: str,
    body: str,
    *,
    src_fname: str = 'F',
    globals: Optional[dict] = None,
) -> Callable:
    body = textwrap.dedent(body)
    code = compile(body, "<string>", "exec")
    if globals is None:
        globals = {}

    func_code = None
    for obj in code.co_consts:
        if isinstance(obj, types.CodeType) and (obj.co_name == name or obj.co_name == src_fname):
            func_code = obj

    if func_code is None:
        raise RuntimeError(f'Cannot find function {name} or {src_fname} in compiled code:\n{body}')

    return types.FunctionType(func_code, globals, name)


def emulate(
    wrapper: Callable,
    wrapped: Callable,
    assigned=functools.WRAPPER_ASSIGNMENTS,
    updated=functools.WRAPPER_UPDATES,
) -> Callable:
    assigned = assigned + ('__signature__', '__defaults__', '__kwdefaults__')
    return functools.update_wrapper(wrapper, wrapped, assigned=assigned, updated=updated)


def wraps(
    wrapped: Callable,
    assigned=functools.WRAPPER_ASSIGNMENTS,
    updated=functools.WRAPPER_UPDATES,
) -> Callable:
    return functools.partial(emulate, wrapped=wrapped, assigned=assigned, updated=updated)


def _call_fragment(sig: inspect.Signature) -> str:
    fragments = []
    P = inspect.Parameter
    for name, p in sig.parameters.items():
        if p.kind in {P.POSITIONAL_ONLY}:
            fragments.append(name)
        elif p.kind in {P.KEYWORD_ONLY, P.POSITIONAL_OR_KEYWORD}:
            fragments.append(f'{name}={name}')
        elif p.kind == P.VAR_POSITIONAL:
            fragments.append(f'*{name}')
        elif p.kind == P.VAR_KEYWORD:
            fragments.append(f'**{name}')

    return ','.join(fragments)


def decorative(*, name: str, f: Optional[Callable] = None) -> Callable:
    def _inner(f: Callable) -> Callable:
        sig = inspect.signature(f)

        assert name in sig.parameters, f'{f!r} has no argument {name!r}'
        assert sig.parameters[name].default is None, \
            f'Argument {name!r} should be keyword and default to None'

        return emulate(
            make_function(
                f.__name__,
                f'''
                def {f.__name__}{str(sig)}:
                    def _decorator({name}):
                        return ___WRAPPED___({_call_fragment(sig)})

                    return _decorator if {name} is None else _decorator({name})
                ''',
                globals={'___WRAPPED___': f},
            ), f
        )

    return _inner if f is None else _inner(f)
