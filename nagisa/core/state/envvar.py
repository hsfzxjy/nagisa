import os
import ast
import glob
import typing
import traceback
import pathlib
import logging

from nagisa.core.state.scheme import SchemeNode
from nagisa.core import primitive
from nagisa.core.primitive import ast as prim_ast
from nagisa.core.primitive.typing import str_to_object, cast
from nagisa.core.misc.io import resolve_until_exists

logger = logging.getLogger(__name__)


def object_from_envvar(name, T, default=None):
    if name not in os.environ:
        return default

    obj = cast(str_to_object(os.environ[name]), T)
    if obj is primitive.Malformed and T is str:
        return os.environ[name]

    return obj


class _EnvvarRegistry:

    __instance = None

    def __new__(cls):
        if cls.__instance is not None:
            return __instance
        cls.__instance = object.__new__(cls)

        cls.__instance._store = None

        return cls.__instance

    def _parse_Call(self, node: ast.Call, func_names: [str]):
        if (not isinstance(node.func, ast.Name)
                or node.func.id not in func_names):
            return

        env_name = prim_ast.cast(node.args[0], str)
        if env_name is None:
            return

        keywords = {n.arg: n.value for n in node.keywords}
        if not set(keywords).issubset({"T", "default"}):
            return

        T = str
        if "T" in keywords:
            T = prim_ast.parse_type(keywords["T"])

        if T is prim_ast.Malformed:
            return

        return env_name, T

    __acceptable_func_names = ("option", "envvar_option", "envvar_op", "envop")

    def sync_with(self, scheme_node: SchemeNode):
        if self._store is not None:
            raise RuntimeError("Cannot call `sync_with()` more than once.")

        self._store = scheme_node

    def scan(
        self,
        dirname=".",
        func_names=__acceptable_func_names,
        caller_level=-2
    ):

        if self._store is None:
            raise RuntimeError(
                "`scan()` should be called after `sync_with()`."
            )

        start_dir = resolve_until_exists(
            dirname, caller_level=caller_level - 1
        )
        if dirname is None:
            logger.warn(
                "`dirname` {!r} resolved to nothing, scanning skipped."
                .format(dirname)
            )
            return

        func_names = set(func_names) | set(self.__acceptable_func_names)
        for py_file in start_dir.glob("**/*.py"):
            try:
                nodes = ast.walk(ast.parse(py_file.read_text(), py_file))
            except OSError:
                continue
            for node in nodes:
                if not isinstance(node, ast.Call):
                    continue

                parsed_result = self._parse_Call(node, func_names)
                if parsed_result is None:
                    continue

                name, T = parsed_result
                env_value = object_from_envvar(name, T, default=None)
                self._store.entry(
                    name,
                    self._store.__class__(type_=(T, None), default=env_value),
                )


_registry = _EnvvarRegistry()


def option(envvar_name, *, T=str, default=None):
    if _registry._store is None:
        logger.warn("Envvar tracking is not enabled.")
        return object_from_envvar(envvar_name, T, default)

    return getattr(_registry._store, envvar_name)
