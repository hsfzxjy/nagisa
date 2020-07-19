import unittest

from nagisa.torch.data._registries import ResourceItemRegistry
from nagisa.core.misc.cache import Scope


class TestRegisterAndSelect(unittest.TestCase):
    def test_register(self):
        reg = ResourceItemRegistry("")

        @reg.r
        def foo(cfg, meta, bar1, bar2):
            pass

        f = reg.select("foo", None, None)
        self.assertIs(f, foo)

        @reg.r("another_foo")
        def foo(cfg, meta, bar1, bar2):
            pass

        f = reg.select("another_foo", None, None)
        self.assertIs(f, foo)

    def test_when(self):
        reg = ResourceItemRegistry("")

        @reg.r("foo")
        @reg.when(lambda c, m: c == "bar")
        def foo1(cfg, meta):
            return "bar"

        @reg.r("foo")
        @reg.when(lambda c, m: m == "baz")
        def foo2(cfg, meta):
            return "baz"

        @reg.r("foo")
        def foo3(cfg, meta):
            return "default"

        self.assertIs(reg.select("foo", "bar", None), foo1)
        self.assertIs(reg.select("foo", None, "baz"), foo2)
        self.assertIs(reg.select("foo", None, None), foo3)

    def test_multi_when(self):
        reg = ResourceItemRegistry("")

        @reg.r
        @reg.when(lambda c, m: c == "bar")
        @reg.when(lambda c, m: c == "baz")
        def foo(cfg, meta):
            return cfg

        self.assertIs(reg.select("foo", "bar", None), foo)
        self.assertIs(reg.select("foo", "baz", None), foo)
        self.assertIsNone(reg.select("foo", "boom", None))

    def test_bad_signature(self):
        reg = ResourceItemRegistry("")

        with self.assertRaises(RuntimeError):

            @reg.r
            @reg.when(lambda c, m, g: c)
            def foo(cfg, meta):
                pass

    def test_scope(self):
        reg = ResourceItemRegistry("")

        @reg.r
        def foo(cfg, meta, id):
            pass

        self.assertEqual(foo.__scope__, Scope.LOCAL)

        @reg.r
        def foo(cfg, meta):
            pass

        self.assertEqual(foo.__scope__, Scope.GLOBAL)

    def test_deps(self):
        reg = ResourceItemRegistry("")

        @reg.r
        def foo(cfg, meta, dep1, dep2, dep3):
            pass

        self.assertEqual(foo.__deps__, ("dep1", "dep2", "dep3"))

        @reg.r
        def foo(cfg, meta, id, dep1, dep2, dep3):
            pass

        self.assertEqual(foo.__deps__, ("dep1", "dep2", "dep3"))
