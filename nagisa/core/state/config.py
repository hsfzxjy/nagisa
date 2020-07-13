import functools
import argparse
from nagisa.core.state import envvar
from nagisa.core.state.scheme import SchemeNode
from nagisa.utils.misc.functools import adapt_params_spec
from nagisa.utils.primitive.typing import cast, str_to_object, Malformed


class ConfigNode(SchemeNode):

    __slots__ = []
    __instance = None

    @classmethod
    def _parse_attributes(cls, ns, attributes):
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
            arg_name = entry._meta.attributes.arg
            if arg_name is None or not hasattr(ns, arg_name):
                return
            directives.append((".".join(path), getattr(ns, arg_name)))

        self._walk([], _visitor)
        self._merge_from_directives(directives, ext_syntax=False)

        return self

    def merge_from_envvar(self):

        directives = []

        def _visitor(path, entry):
            env_name = entry._meta.attributes.env
            if env_name is None or env_name not in envvar.os.environ:
                return
            directives.append(
                (
                    ".".join(path),
                    envvar.object_from_envvar(
                        entry._meta.attributes.env, entry._meta.type
                    ),
                )
            )

        self._walk([], _visitor)
        self._merge_from_directives(directives, ext_syntax=False)

        return self

    def merge_from_remainder(self, remainder, ignore_errors=False, ext_syntax=True):
        if not isinstance(remainder, list):
            raise TypeError(
                "Expect `remainder` to be a list, got {!r}.".format(type(remainder))
            )
        if len(remainder) % 2 != 0:
            raise ValueError("Expect `remainder` to have odd number of elements.")

        self._merge_from_directives(
            zip(
                remainder[::2],
                map(lambda v: str_to_object(v, default=v), remainder[1::2]),
            ),
            ext_syntax,
        )

        return self

    def track_envvar(self, dirname=".", func_names=()):
        self.entry("ENVVAR", self.__class__(is_container=True, attributes=["w"]))
        envvar._registry.sync_with(self.ENVVAR)
        envvar._registry.scan(dirname, caller_level=-4)
        return self

    @classmethod
    def _handle_singleton(cls, instance):
        if cls.__instance is not None:
            raise RuntimeError  # TODO detailed info
        cls.__instance = instance

    @classmethod
    def instance(cls, raise_exc=False):
        if raise_exc and cls.__instance is None:
            raise RuntimeError(
                "This feature requires a singleton config node being initialized."
            )
        return cls.__instance


class ConfigValue(object):

    _Null = object()

    def _wrap(self, value):
        if callable(value) and self.__func_spec is not None:
            return adapt_params_spec(self.__func_spec, value)
        return value

    def __init__(self, name, func_spec=None, default=_Null):
        self.__name = name
        self.__config_path = None
        self.__value = self._Null
        self.__func_spec = func_spec
        self.__default = self._wrap(default)

    def set(self, value):
        if self.__config_path is not None:
            raise RuntimeError(
                f"Cannot set value for {self!r} after its config path being set."
            )
        if self.__value is not self._Null:
            raise RuntimeError(
                f"Cannot set value on {self!r} for more than once."
            )            

        self.__value = self._wrap(value)
        return value

    def set_cfg(self, path):
        if self.__value is not self._Null:
            raise RuntimeError(
                f"Cannot set config path for {self!r} after its value being set."
            )
        if self.__config_path is not None:
            raise RuntimeError(
                f"Cannot set config path on {self!r} for more than once."
            )            
        self.__config_path = path

    def value(self, *args, **kwargs):
        if self.__config_path is not None:
            cfg = ConfigNode.instance()
            if cfg is None:
                raise RuntimeError(
                    f"{self!r} requires a singleton config node being initialized."
                )
            return cfg.value_by_path(self.__config_path)
        elif self.__value is not self._Null or self.__default is not self._Null:
            value = self.__value if self.__value is not self._Null else self.__default
            if callable(value):
                return value(*args, **kwargs)
            return value
        else:
            raise RuntimeError(f"Neither config path nor value is set for {self!r}.")

    func = value
