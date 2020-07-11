import inspect

__all__ = ["match_params"]


def _check_static_and_get_params(f):
    params = inspect.signature(f).parameters
    if not all(
        p.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD,)
        for p in params.values()
    ):
        raise TypeError  # TODO detailed info
    return list(params)


def match_params(f, spec):
    params = _check_static_and_get_params(f)

    L = len(spec)
    if spec[-1] is ...:
        L -= 1
        matched = len(params) >= L
    else:
        matched = len(params) == L
    matched = matched and all(p == s or s == "*" for p, s in zip(params[:L], spec[:L]))

    if not matched:
        raise RuntimeError(
            f"Arguments of function {f.__name__} {params!r} does not match spec {spec!r}."
        )
    return params[L:]

def function_annotator(f, spec, slot_name, init_fn, annotate_fn):
        
    def _decorator(func):        
        value = getattr(func, slot_name, init_fn())
        if f is not None:
            match_params(f, spec)
            value = annotate_fn(value, f)
        setattr(func, slot_name, value)
        return func

    return _decorator