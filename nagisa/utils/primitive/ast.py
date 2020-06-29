import ast
from nagisa.utils.primitive import typing
from nagisa.utils.primitive.malformed import Malformed


def node_to_object(node):
    if isinstance(node, (ast.List, ast.Tuple)):
        return [node_to_object(n) for n in node.elts]
    elif isinstance(node, (ast.Constant, ast.NameConstant)):
        return node.value
    elif isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Str):
        return node.s
    else:
        return Malformed


def cast(node, T):
    return typing.cast(node_to_object(node), T)


def parse_type(node):
    if isinstance(node, ast.Name):
        if node.id in ("int", "float", "str", "bool"):
            return __builtins__[node.id]
        return Malformed
    elif isinstance(node, ast.List):
        if len(node.elts) != 1:
            return Malformed
        return typing.List[parse_type(node.elts[0])]
    else:
        return Malformed
