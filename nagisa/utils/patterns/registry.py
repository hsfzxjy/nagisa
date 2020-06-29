class Registry:
    def __init__(self, name):
        self.__mapping = {}
        self.__name = name

    def _register(self, key, value):
        if key in self.__mapping:
            raise KeyError(
                f"Key {key!r} already registered in <Registry: {self.__name}>"
            )
        self.__mapping[key] = value

    def register(self, key, value=None):
        def _decorator(value):
            self._register(key, value)
            return value

        if value is None:
            return _decorator

        self._register(key, value)
        return value

    def __getitem__(self, key):
        return self.__mapping[key]
