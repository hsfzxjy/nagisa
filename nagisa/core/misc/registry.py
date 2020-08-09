import collections
from nagisa.core.functools import adapt_spec, make_annotator


class Registry:
    def __init__(self, name, unique=True):
        self._mapping_ = {}
        self._name_ = name
        self._unique_ = unique

    def __getitem__(self, key):
        return self._mapping_[key]

    def _check_value_(self, key, value):
        return value

    def _register_(self, key, value):
        if key in self._mapping_ and self._unique_:
            raise KeyError(f"Key {key!r} already registered in <Registry: {self._name_}>")
        value = self._check_value_(key, value)
        self._mapping_[key] = value
        return value

    def register(self, key, value=None):
        def _decorator(value):
            return self._register_(key, value)

        if value is None:
            if hasattr(key, "__name__"):
                value = key
                key = value.__name__
            else:
                return _decorator

        return _decorator(value)

    r = register

    def keys(self):
        return self._mapping_.keys()

    def get(self, key, default=None):
        return self._mapping_.get(key, default)


class Selector:
    # pylint: disable=dangerous-default-value
    def __init__(self, name, cond_spec=[...]):
        self._mapping_ = []
        self._name_ = name
        self._cond_spec_ = cond_spec

    def _check_value_(self, key, value):
        return value

    def _register_(self, cond, value):
        key = adapt_spec(self._cond_spec_, cond)
        value = self._check_value_(key, value)
        self._mapping_.append((key, value))
        return value

    def register(self, key, value=None):
        def _decorator(value):
            return self._register_(key, value)

        if value is None:
            return _decorator

        return _decorator(value)

    r = register

    def select(self, *args):
        for cond, value in self._mapping_:
            if cond(*args):
                return value

        return None


class FuncValueMixin:

    _func_spec_ = [...]

    def _check_value_(self, key, f):
        if getattr(f, "__is_adapter__", False):
            return f

        return adapt_spec(self._func_spec_, f, keep_meta=True)


class FunctionRegistry(FuncValueMixin, Registry):
    pass


class MultiEntryRegistry(Registry):
    def __init__(self, name):
        super().__init__(name)
        self._mapping_ = collections.defaultdict(list)

    def _register_(self, key, value):
        value = self._check_value_(key, value)
        self._mapping_[key].append(value)
        return value


class MultiEntryFunctionRegistry(FunctionRegistry, MultiEntryRegistry):
    pass


def _when_annotator_fn(lst, f):
    lst.append(f)
    return lst


class MultiEntryConditionalFunctionRegistry(MultiEntryFunctionRegistry):

    _when_spec_ = [...]

    @classmethod
    def when(cls, f):
        return make_annotator(f, cls._when_spec_, "__when__", list, _when_annotator_fn)

    def _check_value_(self, key, f):
        new_f = super()._check_value_(key, f)
        self.when(None)(new_f)

        return new_f

    def select(self, key, *args):
        for f in self._mapping_[key]:
            if not f.__when__ or any(cond(*args) for cond in f.__when__):
                return f
        return None


class FunctionSelector(FuncValueMixin, Selector):
    # pylint: disable=dangerous-default-value
    def __init__(self, name, func_spec=[...], cond_spec=[...]):
        super().__init__(name, cond_spec)
        self._func_spec_ = func_spec
