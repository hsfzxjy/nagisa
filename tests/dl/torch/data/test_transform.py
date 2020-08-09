import unittest

from nagisa.core.misc.testing import ReloadModuleTestCase


class BaseTestCase(ReloadModuleTestCase):
    drop_modules = [
        '^nagisa',
    ]
    attach = [
        ['data_module', 'nagisa.dl.torch.data'],
    ]


class TestTransformClass(BaseTestCase):
    def test_basic(self):
        class Square(self.data_module.BaseTransform):
            def _t_num_(self, n, _):
                return n ** 2

        self.assertEqual(Square()({"num": 10, "x": 10}), {"num": 100, "x": 10})

    def test_default(self):
        class Square(self.data_module.BaseTransform):
            def _default_(self, n, k, _):
                if k == "num":
                    return n ** 2
                else:
                    return -1

        self.assertEqual(Square()({"num": 10, "x": 10}), {"num": 100, "x": -1})

    def test_kwargs(self):
        class Pow(self.data_module.BaseTransform):
            class _kwargs_schema_:
                pow: int = 2

            def _t_num_(self, n, *_):
                return n ** self.kwargs.pow

        self.assertEqual(Pow()({"num": 10}), {"num": 100})
        self.assertEqual(Pow(pow=3)({"num": 10}), {"num": 1000})

    def test_check_kwargs(self):
        class Pow(self.data_module.BaseTransform):
            class _kwargs_schema_:
                pow: int = 2

            def _check_kwargs_(self, kwargs):
                kwargs.pow = max(-2, kwargs.pow)

            def _t_num_(self, n, *_):
                return n ** self.kwargs.pow

        self.assertEqual(Pow(pow=-10)({"num": 10}), {"num": 0.01})

    def test_use_me(self):
        class Sqrt(self.data_module.BaseTransform):
            def _use_me_(self, items_dict):
                return items_dict["num"] >= 0

            def _t_num_(self, n, *_):
                return n ** 0.5

        self.assertEqual(Sqrt()({"num": -1}), {"num": -1})
        self.assertEqual(Sqrt()({"num": 4}), {"num": 2})

    def test_given_cfg(self):
        class Pow(self.data_module.BaseTransform):
            def _t_num_(self, n, _):
                return n ** self.cfg.pow

        class _MockCfg:
            pow = 2

        self.assertEqual(Pow(cfg=_MockCfg)({"num": 10}), {"num": 100})

    def test_global_cfg(self):
        class Pow(self.data_module.BaseTransform):
            def _t_num_(self, n, _):
                return n ** self.cfg.pow

        from nagisa.core.state.config import ConfigNode

        @ConfigNode.from_class(singleton=True)
        class Config:
            pow = 2

        Config()

        self.assertEqual(Pow()({"num": 10}), {"num": 100})


class TestApply(BaseTestCase):
    def test_basic_seq(self):
        class Square(self.data_module.BaseTransform):
            def _t_num_(self, n, _):
                return n ** 2

        class Sqrt(self.data_module.BaseTransform):
            def _use_me_(self, items_dict):
                return items_dict["num"] >= 0

            def _t_num_(self, n, _):
                return n ** 0.5

        _seq = []
        self.data_module.trans_seq.set(lambda cfg, meta: _seq)

        _seq = ["sqrt", "square"]
        result = self.data_module.apply_transform(None, None, {"num": -10})
        self.assertEqual(result, {"num": 100})

        _seq = ["square", "sqrt"]
        result = self.data_module.apply_transform(None, None, {"num": -10})
        self.assertEqual(result, {"num": 10})

    def test_init_with_custom_key(self):
        class Square(self.data_module.BaseTransform, key="sqr"):
            def _t_num_(self, n, _):
                return n ** 2

        self.data_module.trans_seq.set(["sqr"])

        result = self.data_module.apply_transform(None, None, {"num": -10})
        self.assertEqual(result, {"num": 100})

    def test_kwargs_mapping(self):
        class Pow(self.data_module.BaseTransform):
            def _t_num_(self, n, _):
                return n ** self.kwargs.pow

        class Root(self.data_module.BaseTransform):
            def _t_num_(self, n, _):
                return n ** (1 / self.kwargs.pow)

        self.data_module.trans_seq.set(["pow", "root"])
        self.data_module.trans_kwargs.set_cfg("data.trans_kwargs")

        from nagisa.core.state.config import ConfigNode

        @ConfigNode.from_class(singleton=True)
        class Config:
            class data:
                @ConfigNode.writable
                class trans_kwargs:
                    pass

        cfg = Config().freeze()

        cfg.data.trans_kwargs = {"pow": {"pow": 4}, "root": {"pow": 2}}
        result = self.data_module.apply_transform(None, None, {"num": -10})
        self.assertEqual(result, {"num": 100})

    def test_kwargs_mapping_static(self):
        class Pow(self.data_module.BaseTransform):
            def _t_num_(self, n, _):
                return n ** self.kwargs.pow

        class Root(self.data_module.BaseTransform):
            def _t_num_(self, n, _):
                return n ** (1 / self.kwargs.pow)

        self.data_module.trans_seq.set(["pow", "root"])
        self.data_module.trans_kwargs.set({"pow": {"pow": 4}, "root": {"pow": 2}})

        result = self.data_module.apply_transform(None, None, {"num": -10})
        self.assertEqual(result, {"num": 100})

    def test_kwargs_mapping_dynamic(self):
        class Pow(self.data_module.BaseTransform):
            def _t_num_(self, n, _):
                return n ** self.kwargs.pow

        class Root(self.data_module.BaseTransform):
            def _t_num_(self, n, _):
                return n ** (1 / self.kwargs.pow)

        self.data_module.trans_seq.set(["pow", "root"])
        self.data_module.trans_kwargs.set({"pow": {"pow": 4}, "root": {"pow": 2}})

        result = self.data_module.apply_transform(None, None, {"num": -10})
        self.assertEqual(result, {"num": 100})

    def test_cache(self):
        times = 0

        class Square(self.data_module.BaseTransform):
            def __init__(self, *args, **kwargs):
                nonlocal times
                super().__init__(*args, **kwargs)
                times += 1

            def _t_num_(self, n, _):
                return n ** 2

        self.data_module.trans_seq.set(["square"])
        result = self.data_module.apply_transform(None, None, {"num": -10})
        self.assertEqual(result, {"num": 100})
        result = self.data_module.apply_transform(None, None, {"num": -10})
        self.assertEqual(result, {"num": 100})
        self.assertEqual(times, 1)
