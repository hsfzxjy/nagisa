import os
import unittest
from nagisa.core.state import schema
from nagisa.core.misc.testing import ReloadModuleTestCase


class TestInit(unittest.TestCase):
    def test_init_empty(self):
        self.assertRaises(AssertionError, schema.SchemaNode)

    def test_init_with_type(self):
        cases = [
            [0, int],
            [0.0, float],
            ["", str],
            [False, bool],
            [[], [int]],
            [[], [float]],
            [[], [str]],
            [[], [bool]],
        ]

        for value, T in cases:
            x = schema.SchemaNode(type_=T)
            self.assertEqual(x._value_, value)

    def test_init_with_default(self):
        cases = [
            [1, int],
            [1.0, float],
            ["baz", str],
            [True, bool],
            [(1, 2), [int]],
            [(1.0, 2), [float]],
            [("baz", "baz2"), [str]],
            [(True, False), [bool]],
            [[1, 2], [int]],
            [[1.0, 2], [float]],
            [["baz", "baz2"], [str]],
            [[True, False], [bool]],
        ]
        for value, T in cases:
            x = schema.SchemaNode(default=value)
            self.assertEqual(x._meta_.type, T)

    def test_init_with_default_and_type(self):
        cases = [
            [1, int],
            [1.0, float],
            ["baz", str],
            [True, bool],
            [[1, 2], [int]],
            [[1.0, 2], [float]],
            [["baz", "baz2"], [str]],
            [[True, False], [bool]],
        ]
        for value, T in cases:
            x = schema.SchemaNode(default=value, type_=T)
            self.assertEqual(x._meta_.type, T)

        cases = [
            [[1, 2], [int]],
            [[1.0, 2], [float]],
            [["baz", "baz2"], [str]],
            [[True, False], [bool]],
        ]
        for value, T in cases:
            schema.SchemaNode(default=value, type_=T)

    def test_init_with_default_and_type_fail(self):
        cases = [
            [1.0, int],
            [True, int],
            ["baz", float],
            [("baz", ), str],
            [0, bool],
            [{}, dict],
        ]
        for value, T in cases:
            with self.assertRaises(
                    AssertionError,
                    msg="`SchemaNode({}, {}) should fail.".format(value, T),
            ):
                schema.SchemaNode(default=value, type_=T)

        cases = [
            [(1, ), [str]],
        ]
        for value, T in cases:
            with self.assertRaises(
                    AssertionError,
                    msg="`SchemaNode({}, {}) should fail.".format(value, T),
            ):
                schema.SchemaNode(default=value, type_=T)


class TestAddEntry(unittest.TestCase):
    def test_add_node(self):
        x = schema.SchemaNode(
            is_container=True,
        ).entry("foo", schema.SchemaNode(default=1)).freeze()

        self.assertEqual(x.foo, 1)

        x = schema.SchemaNode(is_container=True).entry("foo", 1).freeze()
        self.assertEqual(x.foo, 1)

    def test_add_container(self):
        x = (
            schema.SchemaNode(is_container=True
                              ).entry("foo",
                                      schema.SchemaNode(is_container=True).entry("bar", 1)).freeze()
        )
        self.assertEqual(x.foo.bar, 1)

    def test_add_duplicated_node(self):
        with self.assertRaises(AssertionError):
            schema.SchemaNode(is_container=True, ).entry("foo", 1).entry("foo", 2)


class TestAddAlias(unittest.TestCase):
    def test_add_alias(self):
        x = (
            schema.SchemaNode(is_container=True).entry("foo", 1).alias(
                "bar",
                "foo",
            ).alias(
                "baz",
                "bar",
            ).alias(
                "baz_",
                "foo",
            ).freeze()
        )
        self.assertEqual(x.bar, 1)
        self.assertEqual(x.baz, 1)
        self.assertEqual(x.baz_, 1)

    def test_add_broken_alias(self):
        with self.assertRaises(RuntimeError):
            schema.SchemaNode(is_container=True).entry(
                "foo",
                1,
            ).alias(
                "bar",
                "fooo",
            ).alias(
                "baz",
                "bar",
            ).freeze()

    def test_add_duplicated_alias(self):
        with self.assertRaises(AssertionError):
            schema.SchemaNode(is_container=True).entry(
                "foo",
                1,
            ).entry(
                "bar",
                2,
            ).alias(
                "bar",
                "foo",
            ).freeze()

    def test_add_cyclic_alias(self):
        with self.assertRaises(RuntimeError):
            schema.SchemaNode(
                is_container=True,
            ).entry(
                "foo",
                1,
            ).alias(
                "bar",
                "baz",
            ).alias(
                "baz",
                "bar",
            ).freeze()

        with self.assertRaises(RuntimeError):
            schema.SchemaNode(is_container=True).entry(
                "foo",
                1,
            ).alias(
                "bar",
                "bar",
            ).freeze()


class TestGetAttr(unittest.TestCase):
    def test_get_attr_fail(self):
        with self.assertRaises(AttributeError):
            schema.SchemaNode(is_container=True).entry(
                "foo",
                1,
            ).freeze().fooo


class TestSetAttr(unittest.TestCase):
    def test_set_attr_readonly(self):
        with self.assertRaises(AttributeError):
            schema.SchemaNode(is_container=True).entry(
                "foo",
                1,
            ).freeze().foo = 2

    def test_set_attr_writable(self):
        x = schema.SchemaNode(is_container=True).entry(
            "foo",
            schema.SchemaNode(default=1, attributes="writable"),
        ).freeze()

        x.foo += 1
        self.assertEqual(x.foo, 2)

        x = schema.SchemaNode(is_container=True).entry(
            "foo",
            schema.SchemaNode(default=(1, ), attributes="writable"),
        ).freeze()

        x.foo += (2, )
        self.assertEqual(x.foo, [1, 2])
        x.foo = ()
        self.assertEqual(x.foo, [])

    def test_set_attr_wrong_type(self):
        with self.assertRaises(TypeError):
            schema.SchemaNode(
                is_container=True
            ).entry("foo", schema.SchemaNode(default=(1, ),
                                             attributes="writable")).freeze().foo = ["1"]

        with self.assertRaises(TypeError):
            schema.SchemaNode(is_container=True
                              ).entry("foo",
                                      schema.SchemaNode(default=1,
                                                        attributes="writable")).freeze().foo = 1.0

    def test_set_attr_free_container(self):
        x = schema.SchemaNode(is_container=True).entry(
            "foo",
            schema.SchemaNode(is_container=True, attributes="writable"),
        ).freeze()

        x.foo.bar = 1
        x.foo.baz = {"boom": [12]}
        self.assertEqual(x.foo.bar, 1)
        self.assertEqual(x.foo.baz.boom, [12])

        x.foo.bar += 1
        x.foo.baz.boom += [13]
        x.foo.baz.biu = "biu"
        self.assertEqual(x.foo.bar, 2)
        self.assertEqual(x.foo.baz.boom, [12, 13])
        self.assertEqual(x.foo.baz.biu, "biu")

    def test_set_attr_free_container_fail(self):
        x = schema.SchemaNode(is_container=True).entry(
            "foo",
            schema.SchemaNode(is_container=True, attributes="writable"),
        ).freeze()

        x.foo.bar = 1
        with self.assertRaises(TypeError):
            x.foo.bar += 1.2

        with self.assertRaises(TypeError):
            x.foo.bar = {"baz": 1}

    def test_set_attr_free_container_dict(self):
        x = schema.SchemaNode(is_container=True).entry(
            "foo",
            schema.SchemaNode(is_container=True, attributes="w"),
        ).freeze()

        x.foo = {"bar": 1}
        self.assertEqual(x.value_dict(), {"foo": {"bar": 1}})
        x.foo = {"baz": 2}
        self.assertEqual(x.value_dict(), {"foo": {"baz": 2}})

        with self.assertRaises(TypeError) as cm:
            x.foo = 1
        self.assertEqual(
            str(cm.exception),
            "Expect value to be a dict for container entry 'foo', got <class 'int'>",
        )

    def test_set_attr_container_dict_fail(self):
        x = schema.SchemaNode(is_container=True).entry(
            "foo",
            schema.SchemaNode(is_container=True),
        ).freeze()

        with self.assertRaises(AttributeError) as cm:
            x.foo = {"bar": 1}
            self.assertEqual(str(cm.exception), "Cannot update a read-only entry 'foo'.")

    def test_set_attr_before_frozen(self):
        x = schema.SchemaNode(is_container=True).entry("foo", 1)
        x.foo = 2


class TestVerbose(unittest.TestCase):
    def test_str(self):
        x = schema.SchemaNode(is_container=True).entry(
            "foo",
            1,
        ).entry(
            "bar",
            schema.SchemaNode(is_container=True).entry(
                "baz",
                "test",
            ).entry(
                "baz_list",
                ["test"],
            ),
        ).freeze()

        self.assertEqual(
            str(x),
            "foo: (int) 1\n"
            "bar:\n"
            "  baz: (str) test\n"
            "  baz_list: ([str]) ['test']\n",
        )


class TestDeclaritveConstructor(unittest.TestCase):
    def test_from_class(self):
        @schema.SchemaNode.from_class
        class Config:
            foo: [str]

            class bar:
                baz: ["writable"] = 1.0

        x = Config().freeze()
        x.bar.baz = 3.14
        self.assertEqual(str(x), "foo: ([str]) []\n" "bar:\n" "  baz: (float) 3.14\n")

    def test_from_class_writable_container(self):
        @schema.SchemaNode.from_class
        class Config:
            foo: [str]

            @schema.SchemaNode.writable
            class bar:
                pass

        x = Config().freeze()
        x.bar.baz = 3.14
        self.assertEqual(str(x), "foo: ([str]) []\n" "bar:\n" "  baz: (float) 3.14\n")

    def test_from_class_alias(self):
        @schema.SchemaNode.from_class
        class Config:
            foo: int
            bar: "foo"

        x = Config().freeze()
        self.assertEqual(str(x), "foo: (int) 0\n" "bar -> foo\n")
        self.assertEqual(x.bar, 0)

    def test_from_class_type_attributes(self):
        @schema.SchemaNode.from_class
        class Config:
            foo: [float, "writable"] = 9

        x = Config().freeze()
        x.foo = 3.14
        self.assertEqual(str(x), "foo: (float) 3.14\n")


class TestRepr(unittest.TestCase):
    def test_repr(self):
        @schema.SchemaNode.from_class
        class Config:
            pass

        self.assertEqual(str(Config), "<SchemaNode Builder>")


class TestMerge(unittest.TestCase):
    @schema.SchemaNode.from_class
    class Config:
        foo_1: int
        foo_2: [str]

        class sub:
            foo_3: bool
            foo_4: [float]

    def test_merge_from_dict(self):
        dct = {"foo_1": 42, "foo_2": ["bar"], "sub": {"foo_3": True, "foo_4": [123]}}
        cfg = self.Config().merge_from_dict(dct).freeze()

        self.assertEqual(cfg.value_dict(), dct)

    def test_merge_from_dict_attributeerror(self):
        dct = {"foo_1": 42, "foo_2": ["bar"], "sub": {"foo_3": True, "foo_5": [123]}}

        with self.assertRaises(AttributeError) as cm:
            cfg = self.Config().merge_from_dict(dct).freeze()
        self.assertEqual(
            str(cm.exception),
            "Adding extra entries 'foo_5' to read-only container 'sub' is forbidden",
        )

    def test_merge_from_dict_typeerror(self):
        dct = {"foo_1": 42, "foo_2": ["bar"], "sub": 123}

        with self.assertRaises(TypeError) as cm:
            cfg = self.Config().merge_from_dict(dct).freeze()
        self.assertEqual(
            str(cm.exception),
            "Expect value to be a dict for container entry 'sub', got <class 'int'>",
        )

    def test_merge_from_dict_writable_container(self):
        @schema.SchemaNode.from_class
        class Config:
            @schema.SchemaNode.writable
            class sub:
                pass

        cfg = Config().merge_from_dict({"sub": {"foo": "bar"}}).freeze()
        self.assertEqual(cfg.value_dict(), {"sub": {"foo": "bar"}})

    def test_load_from_file(self):
        cfg = self.Config().merge_from_file("yaml_example/a/b/c.yaml").freeze()
        self.assertEqual(
            cfg.value_dict(),
            {
                "sub": {
                    "foo_3": False,
                    "foo_4": [12.0]
                },
                "foo_1": 12,
                "foo_2": ["bar"]
            },
        )

        cfg = self.Config().merge_from_file("yaml_example/a.yaml").freeze()
        self.assertEqual(
            cfg.value_dict(),
            {
                "sub": {
                    "foo_3": False,
                    "foo_4": [42.0]
                },
                "foo_1": 0,
                "foo_2": []
            },
        )

    def test_load_from_file_typeerror(self):
        with self.assertRaises(TypeError):
            cfg = self.Config().merge_from_file("yaml_example/a/b.yaml").freeze()


class TestDump(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_fd, self.temp_file = tempfile.mkstemp(suffix='.yml')

    def tearDown(self):
        os.close(self.temp_fd)
        os.remove(self.temp_file)

    def _file_content(self):
        with open(self.temp_file) as f:
            return f.read()

    expected_content = '\n'.join([
        'a: 1',
        'b: false',
        'c: []',
        'd:',
        '  e: 4.2',
        '',
    ])

    @schema.SchemaNode.from_class
    class Config:
        a = 1
        b = False
        c: [str] = []

        class d:
            e = 4.2

    def test_dump_to_filename(self):
        self.Config().dump(self.temp_file)
        self.assertEqual(self._file_content(), self.expected_content)

    def test_dump_to_file_object(self):
        fobj = os.fdopen(self.temp_fd, 'w+', closefd=False)
        self.Config().dump(fobj)
        self.assertEqual(self._file_content(), self.expected_content)
        fobj.seek(0)
        self.assertEqual(fobj.read(), self.expected_content)

    def test_dump_to_stringio(self):
        import io
        fobj = io.StringIO()
        self.Config().dump(fobj)
        fobj.seek(0)
        self.assertEqual(fobj.read(), self.expected_content)


class TestListValue(unittest.TestCase):
    def test_independent_list(self):
        @schema.SchemaNode.from_class
        class Config:
            lst: [[int], 'w'] = [0]

        cfg = Config().freeze()
        cfg.lst.append(1)
        self.assertEqual(cfg.lst, [0, 1])
        cfg = Config().freeze()
        cfg.lst.append(1)
        self.assertEqual(cfg.lst, [0, 1])

    def test_list_mutability(self):
        @schema.SchemaNode.from_class
        class Config:
            lst: [int] = [0]

        cfg = Config()
        cfg.lst.append(1)
        self.assertEqual(cfg.lst, [0, 1])
        cfg.freeze()
        self.assertRaises(RuntimeError, cfg.lst.append, 1)
        self.assertRaises(RuntimeError, cfg.lst.insert, 1, 1)

        @schema.SchemaNode.from_class
        class Config:
            lst: [[int], 'w'] = [0]

        cfg = Config().freeze()
        cfg.lst.append(1)
        self.assertEqual(cfg.lst, [0, 1])
        self.assertRaises(TypeError, cfg.lst.append, "foo")
        self.assertRaises(TypeError, cfg.lst.extend, ["foo"])


class TestSingleton(unittest.TestCase):
    def test_singleton_True(self):
        @schema.SchemaNode.from_class(singleton=True)
        class Config:
            pass

        self.assertIs(Config(), Config())

    def test_singleton_False(self):
        @schema.SchemaNode.from_class(singleton=False)
        class Config:
            pass

        self.assertIsNot(Config(), Config())

    def test_singleton_different_template(self):
        @schema.SchemaNode.from_class(singleton=True)
        class ConfigA:
            pass

        @schema.SchemaNode.from_class(singleton=True)
        class ConfigB:
            pass

        a = ConfigA()
        b = ConfigB()


class TestEqual(unittest.TestCase):
    def test_strict_equal(self):
        @schema.SchemaNode.from_class
        class Config:
            a = 'foo'
            b: [int]
            c: [[str], 'w']

            class d:
                e = False

            f: 'c'

        cfg1, cfg2 = Config(), Config()
        cfg1.c = ['bar']
        cfg2.c = ['bar']
        self.assertEqual(cfg1, cfg2)
        cfg2.c.append('baz')
        self.assertNotEqual(cfg1, cfg2)

    def test_unstrict_equal(self):
        @schema.SchemaNode.from_class
        class Config1:
            a = 'foo'
            b: [int]
            c: [[str], 'w']

            class d:
                e = False

            f: 'c'

        @schema.SchemaNode.from_class
        class Config2:
            a = 'foo'
            b: [int]
            c: [[str]]

            class d:
                e = False

            g: 'd'

        cfg1, cfg2 = Config1(), Config2()
        self.assertTrue(cfg1.equal(cfg2))


class TestDistributed(ReloadModuleTestCase):
    drop_modules = [
        '^nagisa',
    ]
    attach = [
        ['mp_call', 'nagisa.dl.torch.misc.testing:mp_call'],
        ['SchemaNode', 'nagisa.core.state.schema:SchemaNode'],
    ]

    @staticmethod
    def main_test_picklable(cfg, Q, *_):
        cfg.c = ['bar']
        Q.put(cfg)

    def test_pickable(self):
        @self.SchemaNode.from_class
        class Config:
            a = 'foo'
            b: [int]
            c: [[str], 'w']

            class d:
                e = False

        cfg = Config().freeze()
        result = self.mp_call(self.main_test_picklable, args=(cfg, ))
        cfg.c = ['bar']
        self.assertListEqual(result, [cfg] * 4)
