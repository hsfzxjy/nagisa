import types
import unittest

from nagisa.core import functools


def _make_function(params):
    func_code = compile(f"""def f({', '.join(params)}): pass""", "<string>", "exec")
    return types.FunctionType(func_code.co_consts[0], {}, "f")


class Test_adapt(unittest.TestCase):
    def test_basic(self):
        @functools.adapt(["a", "b"], args=["a.0", "a.1", "a.2"])
        def f(a, b, c):
            return (a, b, c)

        self.assertEqual(
            f([1, 2, 3], object()),
            (1, 2, 3),
        )

        @functools.adapt(["a", "b"], kwargs={"a": "a.0", "b": "a.1", "c": "a.2"})
        def f(a, b, c):
            return (a, b, c)

        self.assertEqual(
            f([1, 2, 3], object()),
            (1, 2, 3),
        )

        @functools.adapt(
            ["a", "b"],
            args=["a.0"],
            kwargs={
                "b": "a.1",
                "c": "a.2"
            },
        )
        def f(a, b, c):
            return (a, b, c)

        self.assertEqual(
            f([1, 2, 3], object()),
            (1, 2, 3),
        )


class Test_adapt_spec(unittest.TestCase):
    def test_basic(self):
        @functools.adapt_spec(["c", "d?", "*", ...])
        def f(c, e, f, g, h):
            return c, e, f, g, h

        self.assertEqual(
            f(1, 2, 3, 4, 5, 6),
            (1, 3, 4, 5, 6),
        )
