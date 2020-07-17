Malformed = type("Malformed", (), {"__repr__": lambda _: "primitive.Malformed"})()


class MalformedValueError(Exception):
    pass
