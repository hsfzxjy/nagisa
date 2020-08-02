import types
import unittest
from nagisa.core import functools


def _make_function(params):
    func_code = compile(f"""def f({', '.join(params)}): pass""", "<string>", "exec")
    return types.FunctionType(func_code.co_consts[0], {}, "f")


class Test_match_spec(unittest.TestCase):
    def test_basic(self):
        cases = [
            [
                (["a", "b", "c"], ["a", "b", "c"]),
                ([], ["a", "b", "c"], ["a", "b", "c"]),
            ],
            [
                (["a", "b", "c"], ["a", "b", "c", ...]),
                ([], ["a", "b", "c"], ["a", "b", "c"]),
            ],
            [
                (["a", "b", "c"], ["a", "b", ...]),
                (["c"], ["a", "b", "_"], ["a", "b", "_"]),
            ],
            [
                (["a", "b"], ["a?", "b"]),
                ([], ["a", "b"], ["a", "b"]),
            ],
            [
                (["b"], ["a?", "b"]),
                ([], ["a", "b"], ["b"]),
            ],
            [
                (["a"], ["a", "b?"]),
                ([], ["a", "b"], ["a"]),
            ],
            [
                ([], ["a?", "b?"]),
                ([], ["a", "b"], []),
            ],
            [
                (["a", "bb"], ["a | aa", "b | bb"]),
                ([], ["a", "b"], ["a", "b"]),
            ],
            [
                (["b", "bb"], ["a | b", "b | bb"]),
                ([], ["a", "b"], ["a", "b"]),
            ],
            [
                (["a", "c", "b"], ["a", "*", "b"]),
                ([], ["a", "_", "b"], ["a", "_", "b"]),
            ],
            [
                (["_", "c", "b"], ["_", "*", "b"]),
                ([], ["_", "__", "b"], ["_", "__", "b"]),
            ],
            [
                (["c", "b"], ["a?", "*", "b"]),
                ([], ["a", "_", "b"], ["_", "b"]),
            ],
            [
                (["c", "b", "e", "f"], ["a?", "*", "b", ...]),
                (
                    ["e", "f"],
                    ["a", "_", "b", "__", "___"],
                    ["_", "b", "__", "___"],
                ),
            ],
            [
                (["c", "e", "f"], ["*", "b?", ...]),
                (["e", "f"], ["_", "b", "__", "___"], ["_", "__", "___"]),
            ],
            [
                (["bb", "b"], ["a?", "b?", ...]),
                (["bb", "b"], ["a", "b", "_", "__"], ["_", "__"]),
            ],
        ]

        for (params, spec), (remaining, adapter_params, mapping) in cases:
            f = _make_function(params)
            result = functools.match_spec(spec, f)
            expected = (
                remaining,
                adapter_params,
                mapping,
            )
            self.assertEqual(result, expected, msg=f"params = {params!r}, spec={spec!r}")

    def test_bad_spec(self):
        cases = [
            ["a|"],
            ["1a"],
            ["*?"],
            [..., "a"],
            [..., ...],
        ]

        f = _make_function([])
        for spec in cases:
            with self.assertRaises(AssertionError, msg=f"spec = {spec!r}"):
                functools.match_spec(spec, f)

    def test_fail(self):
        cases = [
            [["b"], ["a|b?", "b"]],
            [["bb"], ["b?"]],
        ]

        for params, spec in cases:
            f = _make_function(params)
            with self.assertRaises(
                    RuntimeError,
                    msg=f"params = {params!r}, spec = {spec!r}",
            ):
                functools.match_spec(spec, f)
