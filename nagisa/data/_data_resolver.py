import contextlib
from collections import deque

from nagisa.misc.cache import ScopedCache, Scope

from ._registries import Resource, Item

IDLIST_RES_NAME = "id_list"


class DataResolver(object):
    def __init__(self, cfg, meta):
        self.cfg, self.meta = cfg, meta
        self.__cache = ScopedCache()
        self.__dep_checked = False

    def _check_resource_dep(self, path, expected_scope, dep_mapping):
        res_key = path[-1]
        if res_key not in dep_mapping:
            res_f = Resource.select(res_key, self.cfg, self.meta)
            if res_f is None:
                raise RuntimeError  # TODO
            dep_mapping[res_key] = res_f
        res_f = dep_mapping[res_key]

        if expected_scope is not None and expected_scope > res_f.__scope__:
            raise RuntimeError  # TODO

        if expected_scope is None:
            expected_scope = res_f.__scope__

        for dep in res_f.__deps__:
            if dep in path:
                raise RuntimeError  # TODO
            self._check_resource_dep(path + [dep], expected_scope, dep_mapping)

    def _check_item_dep(self, item_key, dep_mapping):
        path = [item_key]
        item_f = Item.select(item_key, self.cfg, self.meta)
        item_scope = item_f.__scope__

        for res_key in item_f.__deps__:
            self._check_resource_dep([res_key], item_scope, dep_mapping)

    def _check_dep(self):
        if self.__dep_checked:
            return

        dep_mapping = {}
        for res_key in Resource.keys():
            expected_scope = None
            if res_key == IDLIST_RES_NAME:
                expected_scope = Scope.GLOBAL
            self._check_resource_dep([res_key], expected_scope, dep_mapping)

        for item_key in Item.keys():
            self._check_item_dep(item_key, dep_mapping)

        self.__dep_checked = True

    def _invoke(self, f, id, deps):
        if f.__scope__ == Scope.LOCAL:
            return f(self.cfg, self.meta, id, *deps)
        elif f.__scope__ == Scope.GLOBAL:
            return f(self.cfg, self.meta, *deps)

    def _get_item(self, id, item_key):
        f = Item.select(item_key, self.cfg, self.meta)
        deps = [self._get_resource(id, dep_name) for dep_name in f.__deps__]
        return self._invoke(f, id, deps)

    def _get_resource(self, id, res_key):
        f = Resource.select(res_key, self.cfg, self.meta)

        cache_key = {
            Scope.LOCAL: ("resource", res_key, id),
            Scope.GLOBAL: ("resource", res_key),
        }[f.__scope__]

        cached = self.__cache.get(cache_key)
        if cached is not self.__cache.Null:
            return cached

        deps = [self._get_resource(id, dep_name) for dep_name in f.__deps__]
        computed = self._invoke(f, id, deps)
        self.__cache.set(cache_key, computed, scope=f.__scope__)
        return computed

    def get_item(self, id, item_key):
        self._check_dep()
        return self._get_item(id, item_key)

    def get_id_list(self):
        self._check_dep()
        return self._get_resource(None, IDLIST_RES_NAME)

    @contextlib.contextmanager
    def new_scope(self):
        with self.__cache.new_scope():
            yield

