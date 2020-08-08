import re


# See https://stackoverflow.com/a/1176023/3278171
def camel_to_snake(name):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def isidentifier(name):
    return isinstance(name, str) and name.isidentifier()


def isaccessor(name):
    return isinstance(name, str) and all(x.isidentifier() or x.isdigit() for x in name.split("."))


def is_dunder(name):
    """Returns True if a __dunder__ name, False otherwise."""
    return len(name) > 4 and name[:2] == name[-2:] == '__' and name[2] != '_' and name[-3] != '_'


def is_sunder(name):
    """Returns True if a _sunder_ name, False otherwise."""
    return len(name) > 2 and name[0] == name[-1] == '_' and name[1:2] != '_' and name[-2:-1] != '_'
