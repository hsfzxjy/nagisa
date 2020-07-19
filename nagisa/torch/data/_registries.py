import enum
import inspect
import collections
from functools import partial
from nagisa.core.misc.cache import Scope
from nagisa.core.misc.registry import MultiEntryConditionalFunctionRegistry, Registry
from nagisa.core.misc.functools import function_annotator

__all__ = [
    "Resource",
    "Item",
    "Collate",
]


class ResourceItemRegistry(MultiEntryConditionalFunctionRegistry):

    _function_spec = ["cfg | c?", "meta | m?", ...]
    _when_spec = ["cfg | c?", "meta | m?"]

    def _check_value(self, key, f):
        new_f = super()._check_value(key, f)
        deps = new_f.__remaining__
        if deps and deps[0] == "id":
            scope = Scope.LOCAL
            deps = deps[1:]
        else:
            scope = Scope.GLOBAL
        new_f.__deps__ = tuple(deps)
        new_f.__scope__ = scope

        return new_f


class CollateRegistry(MultiEntryConditionalFunctionRegistry):

    __DEFAULT_NAME = "default"
    _function_spec = ["cfg | c?", "name | n?", "*"]
    _when_spec = ["cfg | c?", "name | n?"]

    def select(self, key, cfg):
        super_select = super().select
        selected = super_select(key, cfg, key)
        if selected is None:
            selected = super_select(self.__DEFAULT_NAME, cfg, key)
        return selected


Resource = ResourceItemRegistry("Resource")
Item = ResourceItemRegistry("Item")
Transform = Registry("Transform")
Collate = CollateRegistry("Collate")
