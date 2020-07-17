import ast
import unittest
from nagisa.core.primitive.typing import List
from nagisa.core.primitive import ast as prim_ast


def str_to_ast_node(stmt):
    return list(ast.walk(ast.parse(stmt)))[2]


class TestParseType(unittest.TestCase):
    def test_basic(self):
        cases = [
            ("int", int),
            ("float", float),
            ("str", str),
            ("bool", bool),
            ("[str]", List[str]),
            ("[int]", List[int]),
            ("[bool]", List[bool]),
            ("[float]", List[float]),
        ]

        for stmt, target in cases:
            self.assertEqual(prim_ast.parse_type(str_to_ast_node(stmt)), target)

    def test_fail(self):
        cases = [
            "intt",
            "(str,)",
            "complex",
        ]
        for stmt in cases:
            self.assertIs(
                prim_ast.parse_type(str_to_ast_node(stmt)), prim_ast.Malformed
            )


class TestNodeToObject(unittest.TestCase):
    def test_basic(self):
        cases = [
            ("42", 42),
            ("42.", 42.0),
            ('"foo"', "foo"),
            ("'foo'", "foo"),
            ('r"foo"', "foo"),
            ("True", True),
            ("None", None),
            ("[42]", [42]),
            ("(42,)", [42]),
            ("[]", []),
            ("()", []),
            ("[12,False]", [12, False]),
        ]
        for stmt, target in cases:
            self.assertEqual(prim_ast.node_to_object(str_to_ast_node(stmt)), target)

    def test_fail(self):
        cases = [
            "str",
            "1+4j",
            "{}",
            "{1,2,3}",
        ]
        for stmt in cases:
            self.assertIs(
                prim_ast.node_to_object(str_to_ast_node(stmt)), prim_ast.Malformed
            )
