import unittest


class TestBase(unittest.TestCase):
    def setUp(self):
        import sys

        for name in list(sys.modules):
            if name.startswith("nagisa.torch.meter"):
                del sys.modules[name]

        from nagisa.torch.meter import meter_base

        self.meters = meter_base


def f(self):
    ...


class TestMeterBase(TestBase):
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

        self.assertRaises(
            RuntimeError, self.meters.build_meter, "meter_like", ()
        )
        self.assertRaises(
            RuntimeError, self.meters.build_meter, "MeterLike", ()
        )
        self.meters.build_meter("MyMeterLike", ())

    def test_register_with_key_list(self):
        class MeterLike(self.meters.MeterBase, key=["MyMeterLike",
                                                    "MyMeterLike2"]):
            reset = update = compute = f

        self.assertRaises(
            RuntimeError, self.meters.build_meter, "meter_like", ()
        )
        self.assertRaises(
            RuntimeError, self.meters.build_meter, "MeterLike", ()
        )
        self.meters.build_meter("MyMeterLike", ())
        self.meters.build_meter("MyMeterLike2", ())

    def test_build_with_class(self):
        class MeterLike(self.meters.MeterBase):
            reset = update = compute = f

        self.meters.build_meter(MeterLike, ())
