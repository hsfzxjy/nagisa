from nagisa.core.state import envvar
from nagisa.core.state.schema import SchemaNode
from nagisa.core.functools import adapt_spec
from nagisa.core.primitive.typing import str_to_object


class ConfigNode(SchemaNode):

    __slots__ = []
    __instance__ = None

    @classmethod
    def _parse_attributes_(cls, ns, attributes):
        env_name = None
        arg_name = None
        for attr in attributes:
            if attr.startswith("env:"):
                env_name = attr.replace("env:", "")
            elif attr.startswith("arg:"):
                arg_name = attr.replace("arg:", "")

        ns.env = env_name
        ns.arg = arg_name

    def merge_from_args(self, ns):
        directives = []

        def _visitor(path, entry):
            arg_name = entry._meta_.attributes.arg
            if arg_name is None or not hasattr(ns, arg_name):
                return
            directives.append((".".join(path), getattr(ns, arg_name)))

        self._walk_((), _visitor)
        self._merge_from_directives_(directives, ext_syntax=False)

        return self

    def merge_from_envvar(self):
        directives = []

        def _visitor(path, entry):
            env_name = entry._meta_.attributes.env
            if env_name is None or env_name not in envvar.os.environ:
                return
            directive = ".".join(path)
            value = envvar.object_from_envvar(entry._meta_.attributes.env, entry._meta_.type)
            directives.append((directive, value))

        self._walk_((), _visitor)
        self._merge_from_directives_(directives, ext_syntax=False)

        return self

    def merge_from_remainder(self, remainder, *, ignore_errors=False, ext_syntax=True):
        if not isinstance(remainder, list):
            raise TypeError(f"Expect `remainder` to be a list, got {type(remainder)!r}.")
        if len(remainder) % 2 != 0:
            raise ValueError("Expect `remainder` to have odd number of elements.")

        self._merge_from_directives_(
            zip(
                remainder[::2],
                map(lambda v: str_to_object(v, default=v), remainder[1::2]),
            ),
            ext_syntax=ext_syntax,
        )

        return self

    def track_envvar(self, dirname=".", func_names=()):
        self.entry("ENVVAR", self.__class__(is_container=True, attributes=["w"]))
        envvar._registry.sync_with(self.ENVVAR)
        envvar._registry.scan(dirname, caller_level=-2, func_names=func_names)
        return self

    @classmethod
    def _handle_singleton_(cls, instance):
        if cls.__instance__ is not None:
            raise RuntimeError("No singleton instance has been initialized")
        cls.__instance__ = instance

    @classmethod
    def instance(cls, raise_exc=False):
        if raise_exc and cls.__instance__ is None:
            raise RuntimeError("This feature requires a singleton config node being initialized")
        return cls.__instance__


class ConfigValue:

    _empty = object()

    def _wrap_(self, value):
        if callable(value) and self.__func_spec__ is not None:
            return adapt_spec(self.__func_spec__, value)
        return value

    def __init__(self, name, func_spec=None, default=_empty):
        self.__name__ = name
        self.__config_path__ = None
        self.__value__ = self._empty
        self.__func_spec__ = func_spec
        self.__default__ = self._wrap_(default)

    def set(self, value):
        if self.__config_path__ is not None:
            raise RuntimeError(f"Cannot set value for {self!r} after its config path being set")
        if self.__value__ is not self._empty:
            raise RuntimeError(f"Cannot set value on {self!r} for more than once")

        self.__value__ = self._wrap_(value)
        return value

    def set_cfg(self, path):
        if self.__value__ is not self._empty:
            raise RuntimeError(f"Cannot set config path for {self!r} after its value being set")
        if self.__config_path__ is not None:
            raise RuntimeError(f"Cannot set config path on {self!r} for more than once")
        self.__config_path__ = path

    def value(self, *args, **kwargs):
        if self.__config_path__ is not None:
            cfg = ConfigNode.instance()
            if cfg is None:
                raise RuntimeError(f"{self!r} requires a singleton config node being initialized")
            return cfg.value_by_path(self.__config_path__)

        if self.__value__ is not self._empty or self.__default__ is not self._empty:
            value = self.__value__ if self.__value__ is not self._empty else self.__default__
            if callable(value):
                return value(*args, **kwargs)
            return value

        raise RuntimeError(f"Neither config path nor value is set for {self!r}")

    func = value


def custom_or_default_cfg(cfg):
    if cfg is None:
        return ConfigNode.instance(raise_exc=True)
    return cfg


@property
def cfg_property(self):
    return custom_or_default_cfg(self._cfg_)
