import functools
import argparse
from nagisa.core.state.scheme import SchemeNode
from nagisa.core.state import envvar
from nagisa.utils.primitive.typing import cast, str_to_object, Malformed
from nagisa.utils.primitive import modifier


class ConfigNode(SchemeNode):

    __slots__ = []

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
        for name, entry in self._entries.items():
            if entry._meta.is_container:
                entry.merge_from_args(ns)
            elif entry._meta.attributes.arg is not None:
                value = getattr(ns, entry._meta.attributes.arg, Malformed)
                if value is not Malformed:
                    entry._update_value(value)
        return self

    def merge_from_envvar(self):
        for name, entry in self._entries.items():
            if entry._meta.is_container:
                entry.merge_from_envvar()
            elif entry._meta.attributes.env is not None:
                value = envvar.object_from_envvar(
                    entry._meta.attributes.env, entry._meta.type
                )
                if value is not None:
                    entry._update_value(value)
        return self

    def merge_from_remainder(
        self, remainder, ignore_errors=False, extended_syntax=True
    ):
        if not isinstance(remainder, list):
            raise TypeError(
                "Expect `remainder` to be a list, got {!r}.".format(type(remainder))
            )
        if len(remainder) % 2 != 0:
            raise ValueError("Expect `remainder` to have odd number of elements.")

        attrsetter = lambda s, n, v: s._entries[n]._update_value(v)
        for directive, value in zip(remainder[::2], remainder[1::2]):
            value = str_to_object(value, default=value)
            try:
                modifier.modify(
                    self, directive, value, extended_syntax, attrsetter,
                )
            except Exception as e:
                if not ignore_errors:
                    raise

        return self

    def track_envvar(self, dirname=".", func_names=()):
        self.entry("ENVVAR", self.__class__(is_container=True, attributes=["w"]))
        envvar._registry.sync_with(self.ENVVAR)
        envvar._registry.scan(dirname, caller_level=-4)
        return self
