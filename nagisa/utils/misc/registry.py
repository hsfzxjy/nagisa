import collections

from .functools import match_params


class Registry:
    def __init__(self, name):
        self._mapping = {}
        self.__name = name

    def _check_value(self, ley, value):
        pass

    def _register(self, key, value):
        if key in self._mapping:
            raise KeyError(
                f"Key {key!r} already registered in <Registry: {self.__name}>"
            )
        self._check_value(key, value)
        self._mapping[key] = value
        return value

    def register(self, key, value=None):
        def _decorator(value):
            self._register(key, value)
            return value

        if value is None:
            if hasattr(key, "__name__"):
                value = key
                key = value.__name__
            else:
                return _decorator

        self._register(key, value)
        return value

    r = register

    def keys(self):
        return self._mapping.keys()

    def __getitem__(self, key):
        return self._mapping[key]


class FunctionRegistry(Registry):

    _function_spec = [...]

    def _get_function_spec(self, key, f):
        pass

    def _check_value(self, key, f):

        spec = self._function_spec
        if spec is None:
            spec = self._get_function_spec(key, f)

        return match_params(f, self._function_spec)


class MultiEntryRegistry(Registry):
    def __init__(self, name):
        super().__init__(name)
        self._mapping = collections.defaultdict(list)

    def _register(self, key, f):
        self._check_value(key, f)
        self._mapping[key].append(f)
        return f


class MultiEntryFunctionRegistry(FunctionRegistry, MultiEntryRegistry):
    ...
