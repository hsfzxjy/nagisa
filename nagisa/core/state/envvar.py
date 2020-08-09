import os
import ast
import typing
import logging

from nagisa.core.state.schema import SchemaNode
from nagisa.core.primitive import typing
from nagisa.core.primitive import ast as prim_ast
from nagisa.core.misc.io import resolve_until_exists

logger = logging.getLogger(__name__)


def object_from_envvar(name, T, default=None):
    if name not in os.environ:
        return default
    env_value = os.getenv(name)

    return typing.cast(env_value, T=T)


class _EnvvarRegistry:

    __instance__ = None
    __acceptable_func_names__ = ("option", "envvar_option", "envvar_op", "envop")

    @classmethod
    def instance(cls):
        return cls.__instance__

    def __new__(cls):
        if cls.__instance__ is not None:
            return cls.__instance__
        cls.__instance__ = object.__new__(cls)

        return cls.__instance__

    def __init__(self):
        self._store_ = None

    @property
    def store(self):
        return self._store_

    def _parse_Call_(self, node: ast.Call, func_names: [str]):
        if (not isinstance(node.func, ast.Name) or node.func.id not in func_names):
            return None

        env_name = prim_ast.cast(node.args[0], str)
        if env_name is None:
            return None

        keywords = {n.arg: n.value for n in node.keywords}
        if not set(keywords).issubset({"T", "default"}):
            return None

        T = str
        if "T" in keywords:
            T = prim_ast.parse_type(keywords["T"])

        if T is prim_ast.Malformed:
            return None

        return env_name, T

    def unsync(self):
        self._store_ = None

    def sync_with(self, schema_node: SchemaNode):
        if self._store_ is not None:
            raise RuntimeError("Cannot call `sync_with()` more than once.")

        self._store_ = schema_node

    def scan(self, dirname=".", func_names=__acceptable_func_names__, caller_level=-1):

        if self._store_ is None:
            raise RuntimeError("`scan()` should be called after `sync_with()`")

        start_dir = resolve_until_exists(dirname, caller_level=caller_level - 1)
        if start_dir is None:
            logger.warning("`dirname` {!r} resolved to nothing, scanning skipped".format(dirname))
            return

        func_names = set(func_names) | set(self.__acceptable_func_names__)
        for py_file in start_dir.glob("**/*.py"):
            try:
                nodes = ast.walk(ast.parse(py_file.read_text(), py_file))
            except OSError:
                continue
            for node in nodes:
                if not isinstance(node, ast.Call):
                    continue

                parsed_result = self._parse_Call_(node, func_names)
                if parsed_result is None:
                    continue

                name, T = parsed_result
                env_value = object_from_envvar(name, T, default=None)
                self._store_.entry(
                    name,
                    self._store_.__class__(T=(T, None), default=env_value),
                )


_registry = _EnvvarRegistry()


# pylint: disable=invalid-envvar-default
def option(envvar_name, *, T=str, default=None):
    env_value = _empty = object()

    env_value = os.getenv(envvar_name, _empty)
    if _registry.store is None:
        logger.warning("Envvar tracking is not enabled")
    else:
        env_value = _registry.store.value_by_path(envvar_name, env_value)

    if env_value is _empty:
        return default

    return typing.cast(env_value, T)
