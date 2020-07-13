import types
import unittest
from nagisa.utils.misc import functools


def _make_function(params):
    func_code = compile(f"""def f({', '.join(params)}): pass""", "<string>", "exec")
    return types.FunctionType(func_code.co_consts[0], {}, "f")


class TestMatchParamsSpec(unittest.TestCase):
    def test_basic(self):
        # fmt:off
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
                (["e", "f"], ["a", "_", "b", "__", "___"], ["_", "b", "__", "___"]),
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
        # fmt:on

        for (params, spec), (remaining, adapter_params, mapping) in cases:
            f = _make_function(params)
            result = functools.match_params_spec(spec, f, simple=False)
            expected = (
                remaining,
                adapter_params,
                functools._ParsedAdapterMapping(mapping, {}),
            )
            self.assertEqual(
                result, expected, msg=f"params = {params!r}, spec={spec!r}"
            )

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
                functools.match_params_spec(spec, f, simple=True)

    def test_fail(self):
        cases = [
            [["b"], ["a|b?", "b"]],
            [["bb"], ["b?"]],
        ]

        for params, spec in cases:
            f = _make_function(params)
            with self.assertRaises(
                RuntimeError, msg=f"params = {params!r}, spec = {spec!r}"
            ):
                functools.match_params_spec(spec, f, simple=True)


class TestMakeAdapter(unittest.TestCase):
    def test_basic(self):
        @functools.make_adapter(["a", "b"], ["a.0", "a.1", "a.2"])
        def f(a, b, c):
            return (a, b, c)

        self.assertEqual(f([1, 2, 3], object()), (1, 2, 3))

        @functools.make_adapter(["a", "b"], {"a": "a.0", "b": "a.1", "c": "a.2"})
        def f(a, b, c):
            return (a, b, c)

        self.assertEqual(f([1, 2, 3], object()), (1, 2, 3))

        @functools.make_adapter(["a", "b"], (["a.0"], {"b": "a.1", "c": "a.2"}),)
        def f(a, b, c):
            return (a, b, c)

        self.assertEqual(f([1, 2, 3], object()), (1, 2, 3))


class TestAdaptParamsSpec(unittest.TestCase):
    def test_basic(self):
        @functools.adapt_params_spec(["c", "d?", "*", ...])
        def f(c, e, f, g, h):
            return c, e, f, g, h

        self.assertEqual(f(1, 2, 3, 4, 5, 6), (1, 3, 4, 5, 6))

