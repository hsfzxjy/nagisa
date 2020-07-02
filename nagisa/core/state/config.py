import functools
import argparse
from nagisa.core.state.scheme import SchemeNode
from nagisa.core.state import envvar
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
    def instance(cls):
        return cls.__instance
