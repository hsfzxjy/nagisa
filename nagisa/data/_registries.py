import enum
import inspect
import collections
from functools import partial
from nagisa.utils.misc.cache import Scope
from nagisa.utils.misc.registry import MultiEntryFunctionRegistry, Registry
from nagisa.utils.misc.functools import function_annotator

__all__ = [
    "Resource",
    "Item",
    "Transform",
    "Collate",
    "when",
]


def _when_annotator_fn(lst, f):
    lst.append(f)
    return lst


def when(f=None, spec=[...]):

    return function_annotator(f, spec, "__when__", list, _when_annotator_fn)


class ResourceItemRegistry(MultiEntryFunctionRegistry):

    _function_spec = ["cfg", "meta", ...]

    def _check_value(self, key, f):
        deps = super()._check_value(key, f)
        if deps and deps[0] == "id":
            scope = Scope.LOCAL
            deps = deps[1:]
        else:
            scope = Scope.GLOBAL
        f.__deps__ = tuple(deps)
        f.__scope__ = scope
        self.when()(f)

    when = partial(when, spec=["*", "*"])

    def select(self, key, cfg, meta):
        for f in self._mapping[key]:
            if not f.__when__ or any(cond(cfg, meta) for cond in f.__when__):
                return f


class CollateRegistry(MultiEntryFunctionRegistry):

    __DEFAULT_NAME = "default"
    _function_spec = ["cfg", "*"]

    def _check_value(self, key, f):
        super()._check_value(key, f)
        self.when()(f)

    when = partial(when, spec=["*"])

    def _select(self, key, cfg):
        for f in self._mapping[key]:
            if not f.__when__ or any(cond(cfg) for cond in f.__when__):
                return f

    def select(self, key, cfg):
        selected = self._select(key, cfg)
        if selected is None:
            selected = self._select(self.__DEFAULT_NAME, cfg)
        return selected


Resource = ResourceItemRegistry("Resource")
Item = ResourceItemRegistry("Item")
Transform = Registry("Transform")
Collate = CollateRegistry("Collate")

