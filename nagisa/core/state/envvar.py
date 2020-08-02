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
from nagisa.core.primitive import typing
from nagisa.core.misc.io import resolve_until_exists

logger = logging.getLogger(__name__)


def object_from_envvar(name, T, default=None):
    typing.is_acceptableT(T, raise_exc=True)

    hit = False
    if _EnvvarRegistry._instance is not None and _EnvvarRegistry._instance._store is not None:
        store = _EnvvarRegistry._instance._store
        try:
            env_value = store.value_by_path(name)
            hit = True
        except AttributeError:
            pass

    if not hit:
        if name not in os.environ:
            return default
        env_value = os.getenv(name)

    if not isinstance(env_value, str):
        obj = typing.cast(env_value, T, check=False, raise_exc=False)
    else:
        obj = typing.cast(typing.str_to_object(env_value), T, check=False, raise_exc=False)

    if obj is primitive.Malformed:
        if typing.unnullT(T) is str:
            return env_value
        else:
            raise ValueError(f'Cannot cast {env_value!r} into {typing.strT(T)}')

    return obj


class _EnvvarRegistry:

    _instance = None

    def __new__(cls):
        if cls._instance is not None:
            return _instance
        cls._instance = object.__new__(cls)

        return cls._instance

    def __init__(self):
        self._store = None

    def _parse_Call(self, node: ast.Call, func_names: [str]):
        if (not isinstance(node.func, ast.Name) or node.func.id not in func_names):
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

    def scan(self, dirname=".", func_names=__acceptable_func_names, caller_level=-1):

        if self._store is None:
            raise RuntimeError("`scan()` should be called after `sync_with()`.")

        start_dir = resolve_until_exists(dirname, caller_level=caller_level - 1)
        if start_dir is None:
            logger.warn("`dirname` {!r} resolved to nothing, scanning skipped.".format(dirname))
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
