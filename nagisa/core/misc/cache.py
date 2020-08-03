import enum
import contextlib


class Cache(object):

    Empty = object()

    def __init__(self):
        self._store_ = {}

    def _encode_key_(self, key):
        if isinstance(key, list):
            return tuple(key)
        return key

    def set(self, key, value):
        key = self._encode_key_(key)
        self._store_[key] = value

    def get(self, key):
        key = self._encode_key_(key)
        return self._store_.get(key, self.Empty)

    def has(self, key):
        return self._encode_key_(key) in self._store_


class Scope(enum.IntEnum):
    LOCAL = enum.auto()
    GLOBAL = enum.auto()


class ScopedCache(Cache):
    def __init__(self):
        super().__init__()
        self.__key_stack__ = [[]]

    def set(self, key, value, scope=Scope.GLOBAL):
        key = self._encode_key_(key)
        super().set(key, value)
        stack_index = {
            Scope.GLOBAL: 0,
            Scope.LOCAL: -1,
        }[scope]
        self.__key_stack__[stack_index].append(key)

    @contextlib.contextmanager
    def new_scope(self):
        self.__key_stack__.append([])

        yield

        for key in self.__key_stack__[-1]:
            del self._store_[key]
        self.__key_stack__.pop(-1)
