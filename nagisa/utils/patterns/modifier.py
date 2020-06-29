import enum

from nagisa.utils.patterns.registry import Registry


class _Action(enum.Enum):

    UPDATE = enum.auto()
    APPEND = enum.auto()
    PREPEND = enum.auto()
    NOTFOUND = enum.auto()
    INVALID = enum.auto()


_ModifierActionRegistry = Registry("ModifierAction")


@_ModifierActionRegistry.register(_Action.UPDATE)
def __update(directive, obj, name, value, attrsetter):
    attrsetter(obj, name, value)


@_ModifierActionRegistry.register(_Action.APPEND)
def __append(directive, obj, name, value, attrsetter):
    target: list = getattr(obj, name, None)
    if not isinstance(target, list):
        raise TypeError(
            "Cannot apply `{!r}` on {!r} type object.".format(directive, type(value))
        )

    target.append(value)


@_ModifierActionRegistry.register(_Action.PREPEND)
def __prepend(directive, obj, name, value, attrsetter):
    target: list = getattr(obj, name, None)
    if not isinstance(target, list):
        raise TypeError(
            "Cannot apply `{!r}` on {!r} type object.".format(directive, type(value))
        )

    target.insert(0, value)


@_ModifierActionRegistry.register(_Action.NOTFOUND)
def __not_found(directive, obj, name, value, attrsetter):
    raise RuntimeError("`{}` not found.".format(directive))


@_ModifierActionRegistry.register(_Action.INVALID)
def __invalid(directive, obj, name, value, attrsetter):
    raise RuntimeError("Invalid directive `{}`.".format(directive))


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


def modify(
    obj, directive: str, value, ext_syntax=True, attrsetter=setattr, attrchecker=hasattr
):
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
