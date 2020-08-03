import enum

from nagisa.core.misc.registry import Registry


class _Action(enum.Enum):
    UPDATE = enum.auto()
    APPEND = enum.auto()
    PREPEND = enum.auto()
    NOTFOUND = enum.auto()
    INVALID = enum.auto()


_ModifierActionRegistry = Registry("ModifierAction")


@_ModifierActionRegistry.r(_Action.UPDATE)
def _update(directive, obj, name, value, attrsetter):
    attrsetter(obj, name, value)


@_ModifierActionRegistry.r(_Action.APPEND)
def _append(directive, obj, name, value, attrsetter):
    target: list = getattr(obj, name, None)
    if not isinstance(target, list):
        raise TypeError(f"Cannot apply {directive!r} on {type(value)!r} type object")

    target.append(value)


@_ModifierActionRegistry.r(_Action.PREPEND)
def _prepend(directive, obj, name, value, attrsetter):
    target: list = getattr(obj, name, None)
    if not isinstance(target, list):
        raise TypeError(f"Cannot apply {directive!r} on {type(value)!r} type object")

    target.insert(0, value)


@_ModifierActionRegistry.r(_Action.NOTFOUND)
def _not_found(directive, obj, name, value, attrsetter):
    raise RuntimeError(f"{directive!r} not found.")


@_ModifierActionRegistry.r(_Action.INVALID)
def _invalid(directive, obj, name, value, attrsetter):
    raise RuntimeError(f"Invalid directive {directive!r}.")


def _resolve_path(obj, dotted_path: str, attrchecker):
    host = obj
    components = dotted_path.split(".")
    for component in components[:-1]:
        if not component.isidentifier():
            raise NameError
        if not attrchecker(host, component):
            raise AttributeError
        host = getattr(host, component)
    return host, components[-1]


def modify(obj, directive: str, value, ext_syntax=True, attrsetter=setattr, attrchecker=hasattr):
    action = _Action.UPDATE
    dotted_path = directive
    if ext_syntax:
        if directive.startswith("+"):
            action = _Action.PREPEND
            dotted_path = directive[1:]
        elif directive.endswith("+"):
            action = _Action.APPEND
            dotted_path = directive[:-1]

    name = None
    try:
        obj, name = _resolve_path(obj, dotted_path, attrchecker)
    except NameError:
        action = _Action.INVALID
    except AttributeError:
        action = _Action.NOTFOUND

    _ModifierActionRegistry[action](directive, obj, name, value, attrsetter)


_empty = object()


def _default_attrgetter(obj, name):
    result = getattr(obj, name, _empty)
    if result is _empty and hasattr(obj, "__getitem__"):
        if name.isdigit():
            try:
                result = obj[int(name)]
            except KeyError:
                result = _empty
        else:
            try:
                result = obj[name]
            except KeyError:
                result = _empty

    if result is _empty:
        raise AttributeError(f"{obj!r} object has no attribute {name!r}")

    return result


def get(obj, path: str, attrgetter=_default_attrgetter):
    for name in path.split("."):
        obj = attrgetter(obj, name)

    return obj
