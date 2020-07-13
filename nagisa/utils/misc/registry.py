import collections


class Registry:
    def __init__(self, name):
        self._mapping = {}
        self.__name = name

    def _check_value(self, key, value):
        return value

    def _register(self, key, value):
        if key in self._mapping:
            raise KeyError(
                f"Key {key!r} already registered in <Registry: {self.__name}>"
            )
        value = self._check_value(key, value)
        self._mapping[key] = value
        return value

    def register(self, key, value=None):
        def _decorator(value):
            return self._register(key, value)

        if value is None:
            if hasattr(key, "__name__"):
                value = key
                key = value.__name__
            else:
                return _decorator

        return _decorator(value)

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
        from .functools import adapt_params_spec

        spec = self._function_spec
        if getattr(f, "__is_adapter__", False):
            return f

        if spec is None:
            spec = self._get_function_spec(key, f)

        return adapt_params_spec(self._function_spec, f, preserve_meta=True)


class MultiEntryRegistry(Registry):
    def __init__(self, name):
        super().__init__(name)
        self._mapping = collections.defaultdict(list)

    def _register(self, key, value):
        value = self._check_value(key, value)
        self._mapping[key].append(value)
        return value


class MultiEntryFunctionRegistry(FunctionRegistry, MultiEntryRegistry):
    ...
