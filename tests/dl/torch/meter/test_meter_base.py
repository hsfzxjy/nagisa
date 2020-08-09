import unittest

from nagisa.core.misc.testing import ReloadModuleTestCase


def f(self):
    ...


class BaseTestCase(ReloadModuleTestCase):
    drop_modules = [
        '^nagisa.dl.torch.meter',
    ]
    attach = [
        ['meters', 'nagisa.dl.torch.meter.meter_base'],
    ]


class TestMeterBase(BaseTestCase):
    def test_subclass(self):
        class MeterLike:

            reset = update = compute = f

        self.assertTrue(issubclass(MeterLike, self.meters.MeterBase))

        class MeterLike(self.meters.MeterBase):
            ...

        self.assertTrue(issubclass(MeterLike, self.meters.MeterBase))

        class NotAMeter:
            reset = compute = f

        self.assertFalse(issubclass(NotAMeter, self.meters.MeterBase))

    def test_register_with___name__(self):
        class MeterLike(self.meters.MeterBase):
            reset = update = compute = f

        self.meters.build_meter("meter_like", ())
        self.meters.build_meter("MeterLike", ())

    def test_register_with_key_string(self):
        class MeterLike(self.meters.MeterBase, key="MyMeterLike"):
            reset = update = compute = f

        self.assertRaises(RuntimeError, self.meters.build_meter, "meter_like", ())
        self.assertRaises(RuntimeError, self.meters.build_meter, "MeterLike", ())
        self.meters.build_meter("MyMeterLike", ())

    def test_register_with_key_list(self):
        class MeterLike(self.meters.MeterBase, key=["MyMeterLike", "MyMeterLike2"]):
            reset = update = compute = f

        self.assertRaises(RuntimeError, self.meters.build_meter, "meter_like", ())
        self.assertRaises(RuntimeError, self.meters.build_meter, "MeterLike", ())
        self.meters.build_meter("MyMeterLike", ())
        self.meters.build_meter("MyMeterLike2", ())

    def test_build_with_class(self):
        class MeterLike(self.meters.MeterBase):
            reset = update = compute = f

        self.meters.build_meter(MeterLike, ())
