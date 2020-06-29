import enum


class _Action(enum.Enum):

    UPDATE = enum.auto()
    APPEND = enum.auto()
    PREPEND = enum.auto()
    NOTFOUND = enum.auto()
    INVALID = enum.auto()


class _register_action:
    mapping = {}

    def __init__(self, action_token):
        self.action_token = action_token

    def __call__(self, f):
        self.mapping[self.action_token] = f
        return f

    @classmethod
    def invoke(cls, action: _Action, *args, **kwargs):
        cls.mapping[action](*args, **kwargs)


@_register_action(_Action.UPDATE)
def __update(directive, obj, name, value, attrsetter):
    attrsetter(obj, name, value)


@_register_action(_Action.APPEND)
def __append(directive, obj, name, value, attrsetter):
    target: list = getattr(obj, name, None)
    if not isinstance(target, list):
        raise TypeError(
            "Cannot apply `{!r}` on {!r} type object.".format(directive, type(value))
        )

    target.append(value)


@_register_action(_Action.PREPEND)
def __prepend(directive, obj, name, value, attrsetter):
    target: list = getattr(obj, name, None)
    if not isinstance(target, list):
        raise TypeError(
            "Cannot apply `{!r}` on {!r} type object.".format(directive, type(value))
        )

    target.insert(0, value)


@_register_action(_Action.NOTFOUND)
def __not_found(directive, obj, name, value, attrsetter):
    raise RuntimeError("`{}` not found.".format(directive))


@_register_action(_Action.INVALID)
def __invalid(directive, obj, name, value, attrsetter):
    raise RuntimeError("Invalid directive `{}`.".format(directive))


def _resolve_path(obj, dotted_path: str):
    host = obj
    components = dotted_path.split(".")
    for component in components[:-1]:
        if not component.isidentifier():
            raise NameError
        if not hasattr(host, component):
            raise AttributeError
        host = getattr(host, component)
    return host, components[-1]


def modify(obj, directive: str, value, extended_syntax=True, attrsetter=setattr):
    action = _Action.UPDATE
    dotted_path = directive
    if extended_syntax:
        if directive.startswith("+"):
            action = _Action.PREPEND
            dotted_path = directive[1:]
        elif directive.endswith("+"):
            action = _Action.APPEND
            dotted_path = directive[:-1]

    name = None
    try:
        obj, name = _resolve_path(obj, dotted_path)
    except NameError:
        action = _Action.INVALID
    except AttributeError:
        action = _Action.NOTFOUND

    _register_action.invoke(action, directive, obj, name, value, attrsetter)
