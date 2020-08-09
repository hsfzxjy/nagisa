import os
import unittest
import contextlib

from nagisa.core.state import envvar


@contextlib.contextmanager
def mock_env(*args):
    assert len(args) % 2 == 0
    new_env = dict(zip(args[::2], args[1::2]))
    old_env = {n: os.environ.get(n) for n in new_env}

    for k, v in new_env.items():
        if v is None and k in os.environ:
            del os.environ[k]
        else:
            os.environ[k] = str(v)

    yield

    for k, v in old_env.items():
        if v is None and k in os.environ:
            del os.environ[k]
        else:
            os.environ[k] = str(v)


class Test_object_from_envvar(unittest.TestCase):
    def test_parse_str(self):
        with mock_env("foo", "bar"):
            self.assertEqual(
                "bar",
                envvar.object_from_envvar("foo", str),
            )
        with mock_env("foo", "'bar'"):
            self.assertEqual(
                "'bar'",
                envvar.object_from_envvar("foo", str),
            )

    def test_parse_num(self):
        with mock_env("foo", "1"):
            self.assertEqual(
                1,
                envvar.object_from_envvar("foo", int),
            )
        with mock_env("foo", "1"):
            self.assertEqual(
                1.0,
                envvar.object_from_envvar("foo", float),
            )
            self.assertIs(
                type(envvar.object_from_envvar("foo", float)),
                float,
            )
        with mock_env("foo", "1" + "0" * 100):
            self.assertEqual(
                10 ** 100,
                envvar.object_from_envvar("foo", int),
            )


class Test_option(unittest.TestCase):
    def test_modify_from_store(self):
        from nagisa.core.state.schema import SchemaNode

        envvar._registry.unsync()
        schema_node = SchemaNode(is_container=True, attributes=["w"]).freeze()
        envvar._registry.sync_with(schema_node)

        with mock_env("FOO1", "['bar']"):
            schema_node.FOO2 = "(True,)"
            schema_node.FOO3 = [42.]
            self.assertEqual(
                envvar.option("FOO1", T=[str]),
                ['bar'],
            )
            self.assertEqual(
                envvar.option("FOO2", T=[bool]),
                [True],
            )
            self.assertRaises(
                TypeError,
                envvar.option,
                "FOO3",
                T=[bool],
            )
            self.assertEqual(
                envvar.option("FOO2", T=(str, None)),
                "(True,)",
            )


class Test_option_scan(unittest.TestCase):
    def setUp(self):
        from nagisa.core.state.schema import SchemaNode

        envvar._registry.unsync()
        self.schema_node = SchemaNode(is_container=True, attributes=["w"])
        envvar._registry.sync_with(self.schema_node)

    def test_scan(self):
        with mock_env(
                "mod_1_foo_1",
                "42",
                "mod_1_foo_3",
                "bar",
                "mod_1_foo_4",
                "[True,False]",
        ):
            envvar._registry.scan("envvar_case_1")
            self.assertEqual(
                self.schema_node.value_dict(),
                {
                    "mod_1_foo_1": 42,
                    "mod_1_foo_2": None,
                    "mod_1_foo_3": "bar",
                    "mod_1_foo_4": [True, False],
                    "mod_1_foo_5": None,
                },
            )
            self.assertEqual(
                self.schema_node.type_dict(),
                {
                    "mod_1_foo_1": (int, None),
                    "mod_1_foo_2": (float, None),
                    "mod_1_foo_3": (str, None),
                    "mod_1_foo_4": ([bool], None),
                    "mod_1_foo_5": (bool, None),
                },
            )
