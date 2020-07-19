import enum
import contextlib


class Cache(object):

    Null = object()

    def __init__(self):
        self._store = {}

    def _encode_key(self, key):
        if isinstance(key, list):
            return tuple(key)
        return key

    def set(self, key, value):
        key = self._encode_key(key)
        self._store[key] = value

    def get(self, key):
        key = self._encode_key(key)
        return self._store.get(key, self.Null)

    def has(self, key):
        return self._encode_key(key) in self._store


class Scope(enum.IntEnum):

    LOCAL = enum.auto()
    GLOBAL = enum.auto()


class ScopedCache(Cache):
    def __init__(self):
        self._store = {}
        self.__key_stack = [[]]

    def set(self, key, value, scope=Scope.GLOBAL):
        key = self._encode_key(key)
        super().set(key, value)
        stack_index = {
            Scope.GLOBAL: 0,
            Scope.LOCAL: -1,
        }[scope]
        self.__key_stack[stack_index].append(key)

    @contextlib.contextmanager
    def new_scope(self):
        self.__key_stack.append([])

        yield

        for key in self.__key_stack[-1]:
            del self._store[key]
        self.__key_stack.pop(-1)
