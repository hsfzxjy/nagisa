import argparse
import unittest

from nagisa.core.state import config
from nagisa.core.misc.testing import ReloadModuleTestCase

from .test_envvar import mock_env


@config.ConfigNode.from_class
class Config:
    foo_1 = 1
    foo_2: ["env:FOO2", "arg:foo2"] = 42.0

    class sub:
        foo_3: ["env:FOO3"] = "bar"
        foo_4: ["arg:foo4"] = [0]

    alias_1: "foo_1"


class Test_merge(unittest.TestCase):
    def test_merge_from_envvar(self):
        with mock_env("FOO2", "36", "FOO3", "baz"):
            config = Config().merge_from_envvar().freeze()
        self.assertEqual(
            config.value_dict(),
            {
                "foo_1": 1,
                "foo_2": 36,
                "sub": {
                    "foo_3": "baz",
                    "foo_4": [0]
                }
            },
        )

        with mock_env("FOO2", "36"):
            config = Config().merge_from_envvar().freeze()
        self.assertEqual(
            config.value_dict(),
            {
                "foo_1": 1,
                "foo_2": 36,
                "sub": {
                    "foo_3": "bar",
                    "foo_4": [0]
                }
            },
        )

    def test_merge_from_args(self):
        config = Config().merge_from_args(argparse.Namespace(foo4=[1])).freeze()
        self.assertEqual(
            config.value_dict(),
            {
                "foo_1": 1,
                "foo_2": 42.0,
                "sub": {
                    "foo_3": "bar",
                    "foo_4": [1]
                }
            },
        )

        config = (Config().merge_from_args(argparse.Namespace(foo4=[1], foo2=36)).freeze())
        self.assertEqual(
            config.value_dict(),
            {
                "foo_1": 1,
                "foo_2": 36,
                "sub": {
                    "foo_3": "bar",
                    "foo_4": [1]
                }
            },
        )

    def test_merge_from_remainder(self):
        remainder = [
            "foo_1",
            "2",
            "sub.foo_4",
            "[1]",
            "+sub.foo_4",
            "0",
            "sub.foo_4+",
            "2",
            "sub.foo_3",
            "remainder",
        ]
        config = Config().merge_from_remainder(remainder).freeze()
        self.assertEqual(
            config.value_dict(),
            {
                "foo_1": 2,
                "foo_2": 42.0,
                "sub": {
                    "foo_3": "remainder",
                    "foo_4": [0, 1, 2]
                },
            },
        )


class TestSingleton(ReloadModuleTestCase):
    drop_modules = [
        '^nagisa.core.state.config',
    ]
    attach = [
        ['config_module', 'nagisa.core.state.config'],
    ]

    def test_singleton(self):
        @self.config_module.ConfigNode.from_class(singleton=True)
        class Config:
            pass

        cfg = Config()
        self.assertIs(
            cfg,
            self.config_module.ConfigNode.instance(),
        )

    def test_singleton_fail(self):
        @self.config_module.ConfigNode.from_class(singleton=True)
        class ConfigA:
            pass

        @self.config_module.ConfigNode.from_class(singleton=True)
        class ConfigB:
            pass

        a = ConfigA()
        with self.assertRaises(RuntimeError):
            ConfigB()
