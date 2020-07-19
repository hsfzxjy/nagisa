import re


# See https://stackoverflow.com/a/1176023/3278171
def camel_to_snake(name):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def isidentifier(name):
    return isinstance(name, str) and name.isidentifier()


def isaccessor(name):

    return isinstance(name, str) and all(
        x.isidentifier() or x.isdigit() for x in name.split(".")
    )
