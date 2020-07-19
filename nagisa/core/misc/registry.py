import collections


class Registry:
    def __init__(self, name, unique=True):
        self._mapping = {}
        self.__name = name
        self.__unique = unique

    def _check_value(self, key, value):
        return value

    def _register(self, key, value):
        if key in self._mapping and self.__unique:
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

    def get(self, key, default=None):
        return self._mapping.get(key, default)


class Selector(object):
    def __init__(self, name, cond_spec=[...]):
        self._mapping = []
        self.__name = name
        self._cond_spec = cond_spec

    def _register(self, cond, value):
        from .functools import adapt_params_spec

        key = adapt_params_spec(self._cond_spec, cond)
        value = self._check_value(key, value)
        self._mapping.append((key, value))
        return value

    def register(self, key, value=None):
        def _decorator(value):
            return self._register(key, value)

        if value is None:
            return _decorator

        return _decorator(value)

    r = register

    def select(self, *args):
        for cond, value in self._mapping:
            if cond(*args):
                return value

        return None


class FunctionValueMixin(object):

    _function_spec = [...]

    def _check_value(self, key, f):
        from .functools import adapt_params_spec

        spec = self._function_spec
        if getattr(f, "__is_adapter__", False):
            return f

        return adapt_params_spec(self._function_spec, f, preserve_meta=True)


class FunctionRegistry(FunctionValueMixin, Registry):
    pass


class MultiEntryRegistry(Registry):
    def __init__(self, name):
        super().__init__(name)
        self._mapping = collections.defaultdict(list)

    def _register(self, key, value):
        value = self._check_value(key, value)
        self._mapping[key].append(value)
        return value


class MultiEntryFunctionRegistry(FunctionRegistry, MultiEntryRegistry):
    pass


def _when_annotator_fn(lst, f):
    lst.append(f)
    return lst


class MultiEntryConditionalFunctionRegistry(MultiEntryFunctionRegistry):

    _when_spec = [...]

    @classmethod
    def when(cls, f):
        from .functools import function_annotator

        return function_annotator(
            f, cls._when_spec, "__when__", list, _when_annotator_fn
        )

    def _check_value(self, key, f):
        new_f = super()._check_value(key, f)
        self.when(None)(new_f)

        return new_f

    def select(self, key, *args):
        for f in self._mapping[key]:
            if not f.__when__ or any(cond(*args) for cond in f.__when__):
                return f


class FunctionSelector(FunctionValueMixin, Selector):
    def __init__(self, name, func_spec=[...], cond_spec=[...]):
        super().__init__(name, cond_spec)
        self._func_spec = func_spec
