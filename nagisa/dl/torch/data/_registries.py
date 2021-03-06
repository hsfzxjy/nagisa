from nagisa.core.misc.cache import Scope
from nagisa.core.misc.registry import MultiEntryConditionalFunctionRegistry, Registry

__all__ = [
    "Resource",
    "Item",
    "Collate",
]


class ResourceItemRegistry(MultiEntryConditionalFunctionRegistry):

    _func_spec_ = ["cfg | c?", "meta | m?", ...]
    _when_spec_ = ["cfg | c?", "meta | m?"]

    def _check_value_(self, key, f):
        new_f = super()._check_value_(key, f)
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
    _func_spec_ = ["cfg | c?", "name | n?", "*"]
    _when_spec_ = ["cfg | c?", "name | n?"]

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
