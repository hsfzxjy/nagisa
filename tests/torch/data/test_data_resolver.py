import unittest
from importlib import import_module


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        import sys

        for n in list(filter(
                lambda x: x.startswith("nagisa.torch.data"),
                sys.modules,
        )):
            del sys.modules[n]

        from nagisa.torch.data import shortcuts
        from nagisa.torch.data._data_resolver import DataResolver

        self.s = shortcuts
        self.DataResolver = DataResolver


class TestCheckDep(BaseTestCase):
    def test_basic(self):
        @self.s.Resource.r
        def res1(id):
            pass

        @self.s.Resource.r
        def res2(id, res1):
            pass

        @self.s.Item.r
        def item1(id, res1, res2):
            pass

        self.DataResolver(None, None)._check_dep()

    def test_cyclic_resource(self):
        @self.s.Resource.r
        def res1(res2):
            pass

        @self.s.Resource.r
        def res2(res1):
            pass

        with self.assertRaises(RuntimeError):
            self.DataResolver(None, None)._check_dep()

    def test_cyclic_resource_with(self):
        @self.s.Resource.r
        def res1(res2):
            pass

        @self.s.Resource.r
        def res2(res1):
            pass

        @self.s.Item.r
        def item(res1):
            pass

        with self.assertRaises(RuntimeError):
            self.DataResolver(None, None)._check_dep()

    def test_cyclic_self(self):
        @self.s.Resource.r
        def res1(res1):
            pass

        with self.assertRaises(RuntimeError):
            self.DataResolver(None, None)._check_dep()

    def test_bad_dep_name(self):
        @self.s.Resource.r
        def res1(bad):
            pass

        with self.assertRaises(RuntimeError):
            self.DataResolver(None, None)._check_dep()

    def test_scope(self):
        @self.s.Resource.r
        def res1():
            pass

        @self.s.Resource.r
        def res2(id, res1):
            pass

        self.DataResolver(None, None)._check_dep()

    def test_bad_scope(self):
        @self.s.Resource.r
        def res1(id):
            pass

        @self.s.Resource.r
        def res2(res1):
            pass

        with self.assertRaises(RuntimeError):
            self.DataResolver(None, None)._check_dep()

    def test_bad_scope_item(self):
        @self.s.Resource.r
        def res1(id):
            pass

        @self.s.Item.r
        def res2(res1):
            pass

        with self.assertRaises(RuntimeError):
            self.DataResolver(None, None)._check_dep()


class TestCache(BaseTestCase):
    def test_cache_global_resource(self):
        times = 0

        @self.s.Resource.r
        def res1():
            nonlocal times
            times += 1

        @self.s.Item.r
        def item1(res1):
            pass

        resolver = self.DataResolver(None, None)
        resolver.get_item(1, "item1")
        self.assertEqual(times, 1)
        resolver.get_item(2, "item1")
        self.assertEqual(times, 1)

    def test_cache_local_resource_no_context(self):
        times = 0

        @self.s.Resource.r
        def res1(id):
            nonlocal times
            times += 1

        @self.s.Item.r
        def item1(id, res1):
            pass

        resolver = self.DataResolver(None, None)
        resolver.get_item(1, "item1")
        self.assertEqual(times, 1)
        resolver.get_item(2, "item1")
        self.assertEqual(times, 2)

        times = 0
        resolver.get_item(1, "item1")
        self.assertEqual(times, 0)

    def test_cache_local_resource_with_context(self):
        times = 0

        @self.s.Resource.r
        def res1(id):
            nonlocal times
            times += 1

        @self.s.Item.r
        def item1(id, res1):
            pass

        resolver = self.DataResolver(None, None)
        with resolver.new_scope():
            resolver.get_item(1, "item1")
            self.assertEqual(times, 1)
        with resolver.new_scope():
            resolver.get_item(1, "item1")
            self.assertEqual(times, 2)
        with resolver.new_scope():
            with resolver.new_scope():
                resolver.get_item(1, "item1")
            resolver.get_item(1, "item1")
            self.assertEqual(times, 4)

    def test_cache_global_resource_with_context(self):
        times = 0

        @self.s.Resource.r
        def res1():
            nonlocal times
            times += 1

        @self.s.Item.r
        def item1(res1):
            pass

        resolver = self.DataResolver(None, None)
        with resolver.new_scope():
            with resolver.new_scope():
                with resolver.new_scope():
                    with resolver.new_scope():
                        resolver.get_item(1, "item1")
                    resolver.get_item(2, "item1")
                resolver.get_item(3, "item1")
            resolver.get_item(4, "item1")

        self.assertEqual(times, 1)

    def test_different_meta(self):
        times = 0

        @self.s.Resource.r
        def res1():
            nonlocal times
            times += 1

        @self.s.Item.r
        def item1(res1):
            pass

        resolver = self.DataResolver(None, meta=1)
        resolver.get_item(1, "item1")
        resolver.get_item(1, "item1")
        resolver = self.DataResolver(None, meta=2)
        resolver.get_item(1, "item1")
        resolver.get_item(1, "item1")

        self.assertEqual(times, 2)


class TestGetIdList(BaseTestCase):
    def test_basic(self):
        @self.s.Resource.r
        def id_list():
            return list(range(10))

        self.assertEqual(self.DataResolver(None, None).get_id_list(), list(range(10)))

    def test_basic_with_dep(self):
        @self.s.Resource.r
        def nums(meta):
            return list(range(meta))

        @self.s.Resource.r
        def id_list(nums):
            return nums

        self.assertEqual(self.DataResolver(None, 10).get_id_list(), list(range(10)))

    def test_bad_scope(self):
        @self.s.Resource.r
        def id_list(id):
            return list(range(10))

        with self.assertRaises(RuntimeError):
            self.DataResolver(None, None).get_id_list()
