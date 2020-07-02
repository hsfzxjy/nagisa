class Registry:
    def __init__(self, name):
        self._mapping = {}
        self.__name = name

    def _register(self, key, value):
        if key in self._mapping:
            raise KeyError(
                f"Key {key!r} already registered in <Registry: {self.__name}>"
            )
        self._mapping[key] = value

    def register(self, key, value=None):
        def _decorator(value):
            self._register(key, value)
            return value

        if value is None:
            if hasattr(key, '__name__'):
                value = key
                key = value.__name__
            else:
                return _decorator

        self._register(key, value)
        return value

    def __getitem__(self, key):
        return self._mapping[key]
