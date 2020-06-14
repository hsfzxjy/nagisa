import unittest
from nagisa.core import scheme

class TestInit(unittest.TestCase):

    def test_init_empty(self):
        self.assertRaises(AssertionError, scheme.SchemeNode)

    def test_init_with_type(self):
        cases = [
            [0, int],
            [0., float],
            ['', str],
            [False, bool],
            [[], scheme.List[int]],
            [[], scheme.List[float]],
            [[], scheme.List[str]],
            [[], scheme.List[bool]],
        ]

        for value, T in cases:
            x = scheme.SchemeNode(type_=T)
            self.assertEqual(x._SchemeNode__value, value)

    def test_init_with_default(self):
        cases = [
            [1, int],
            [1., float],
            ['baz', str],
            [True, bool],
            [(1, 2,), scheme.List[int]],
            [(1., 2,), scheme.List[float]],
            [('baz', 'baz2'), scheme.List[str]],
            [(True, False), scheme.List[bool]],
            [[1, 2,], scheme.List[int]],
            [[1., 2,], scheme.List[float]],
            [['baz', 'baz2'], scheme.List[str]],
            [[True, False], scheme.List[bool]],
        ]
        for value, T in cases:
            x = scheme.SchemeNode(default=value)
            self.assertEqual(
                x._SchemeNode__meta.type,
                T
            )

    def test_init_with_default_and_type(self):
        cases = [
            [1, int],
            [1., float],
            ['baz', str],
            [True, bool],
            [[1, 2,], scheme.List[int]],
            [[1., 2,], scheme.List[float]],
            [['baz', 'baz2'], scheme.List[str]],
            [[True, False], scheme.List[bool]],
        ]
        for value, T in cases:
            x = scheme.SchemeNode(default=value, type_=T)
            self.assertEqual(
                x._SchemeNode__meta.type,
                T
            )

        cases = [
            [[1, 2,], [int]],
            [[1., 2,], [float]],
            [['baz', 'baz2'], [str]],
            [[True, False], [bool]],
        ]
        for value, T in cases:
            scheme.SchemeNode(default=value, type_=T)

    def test_init_with_default_and_type_failure(self):
        cases = [
            [1., int],
            [True, int],
            ['baz', float],
            [('baz',), str],
            [0, bool],
            [{}, dict]
        ]
        for value, T in cases:
            with self.assertRaises(AssertionError, msg='`SchemeNode({}, {}) should fail.'.format(value, T)):
                scheme.SchemeNode(default=value, type_=T)

        cases = [
            [(), scheme.List[str]],
        ]
        for value, T in cases:
            with self.assertRaises(TypeError, msg='`SchemeNode({}, {}) should fail.'.format(value, T)):
                scheme.SchemeNode(default=value, type_=T)

class TestAddEntry(unittest.TestCase):

    def test_add_node(self):
        x = scheme.SchemeNode(
            is_container=True
        ).entry('foo', scheme.SchemeNode(default=1)).finalize()
        self.assertEqual(x.foo, 1)

        x = scheme.SchemeNode(
            is_container=True
        ).entry('foo', 1).finalize()
        self.assertEqual(x.foo, 1)

    def test_add_container(self):
        x = scheme.SchemeNode(
            is_container=True
        ).entry('foo', 
            scheme.SchemeNode(
                is_container=True
            ).entry('bar', 1)
        ).finalize()
        self.assertEqual(x.foo.bar, 1)

    def test_add_duplicated_node(self):
        with self.assertRaises(AssertionError):
            x = scheme.SchemeNode(
                is_container=True
            ).entry('foo', 1).entry('foo', 2)

class TestAddAlias(unittest.TestCase):

    def test_add_alias(self):
        x = scheme.SchemeNode(is_container=True) \
            .entry('foo', 1) \
            .alias('bar', 'foo') \
            .alias('baz', 'bar') \
            .alias('baz_', 'foo') \
            .finalize()
        self.assertEqual(x.bar, 1)
        self.assertEqual(x.baz, 1)
        self.assertEqual(x.baz_, 1)

    def test_add_broken_alias(self):
        with self.assertRaises(RuntimeError):
            x = scheme.SchemeNode(is_container=True) \
                .entry('foo', 1) \
                .alias('bar', 'fooo') \
                .alias('baz', 'bar') \
                .finalize()

    def test_add_duplicated_alias(self):
        with self.assertRaises(AssertionError):
            x = scheme.SchemeNode(is_container=True) \
                .entry('foo', 1) \
                .entry('bar', 2) \
                .alias('bar', 'foo') \
                .finalize()

    def test_add_cyclic_alias(self):
        with self.assertRaises(RuntimeError):
            x = scheme.SchemeNode(is_container=True) \
                .entry('foo', 1) \
                .alias('bar', 'baz') \
                .alias('baz', 'bar') \
                .finalize()

        with self.assertRaises(RuntimeError):
            x = scheme.SchemeNode(is_container=True) \
                .entry('foo', 1) \
                .alias('bar', 'bar') \
                .finalize()

class TestGetAttr(unittest.TestCase):

    def test_get_attr_fail(self):
        with self.assertRaises(AttributeError):
            scheme.SchemeNode(is_container=True) \
                .entry('foo', 1).finalize().fooo

class TestSetAttr(unittest.TestCase):

    def test_set_attr_readonly(self):
        with self.assertRaises(AttributeError):
            scheme.SchemeNode(is_container=True) \
                .entry('foo', 1).finalize().foo = 2

    def test_set_attr_writable(self):
        x = scheme.SchemeNode(is_container=True) \
            .entry('foo', scheme.SchemeNode(default=1, attributes='writable')) \
            .finalize()
        x.foo += 1               
        self.assertEqual(x.foo, 2)

        x = scheme.SchemeNode(is_container=True) \
            .entry('foo', scheme.SchemeNode(default=(1,), attributes='writable')) \
            .finalize()
        x.foo += (2,)
        self.assertEqual(x.foo, [1, 2])
        x.foo = ()
        self.assertEqual(x.foo, [])

    def test_set_attr_wrong_type(self):
        with self.assertRaises(TypeError):
            scheme.SchemeNode(is_container=True) \
                .entry('foo', scheme.SchemeNode(default=(1,), attributes='writable')) \
                .finalize().foo = ['1']

        with self.assertRaises(TypeError):
            scheme.SchemeNode(is_container=True) \
                .entry('foo', scheme.SchemeNode(default=1, attributes='writable')) \
                .finalize().foo = 1.

    def test_set_attr_free_container(self):
        x = scheme.SchemeNode(is_container=True) \
            .entry('foo', scheme.SchemeNode(is_container=True, attributes='writable')) \
            .finalize()

        x.foo.bar = 1
        x.foo.baz = { 'boom': [12] }
        self.assertEqual(x.foo.bar, 1)
        self.assertEqual(x.foo.baz.boom, [12])

        x.foo.bar += 1
        x.foo.baz.boom += [13]
        x.foo.baz.biu = 'biu'
        self.assertEqual(x.foo.bar, 2)
        self.assertEqual(x.foo.baz.boom, [12, 13])
        self.assertEqual(x.foo.baz.biu, 'biu')

    def test_set_attr_free_container(self):
        x = scheme.SchemeNode(is_container=True) \
            .entry('foo', scheme.SchemeNode(is_container=True, attributes='writable')) \
            .finalize()

        with self.assertRaises(RuntimeError):
            x.foo = { 'bar': 1 }

        x.foo.bar = 1
        with self.assertRaises(TypeError):
            x.foo.bar += 1.2

        with self.assertRaises(TypeError):
            x.foo.bar = { 'baz': 1 }
