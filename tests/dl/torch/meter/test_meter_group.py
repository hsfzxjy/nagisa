import unittest

import torch

from nagisa.dl.torch.misc.testing import TorchTestCase
from nagisa.core.misc.testing import ReloadModuleTestCase

t = torch.tensor


class BaseTestCase(ReloadModuleTestCase, TorchTestCase):
    drop_modules = [
        '^nagisa.dl.torch.meter',
    ]
    attach = [
        ['mb', 'nagisa.dl.torch.meter.meter_base'],
        ['mg', 'nagisa.dl.torch.meter.meter_group'],
        ['mbi', 'nagisa.dl.torch.meter.meter_builtins'],
    ]


class TestBaseMeterGroup(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.group = self.mg.BaseMeterGroup()

    def test_is_meter_class(self):
        self.assertTrue(self.mb.is_meter_class(self.mg.BaseMeterGroup))

    def test_add_group_spec_init_only(self):
        self.group.add_group("group1", ["arg1", "arg2"], {"m1": "Avg", "m2": "Avg"})
        self.group.update("group1", inputs={"arg1": 42, "arg2": 2})
        self.assertEqual(self.group.compute("group1"), {
            "m1": t(21.),
            "m2": t(21.),
        })

        self.group.remove_group("group1").add_group("group1", ["arg1", "arg2"], {"m1": ("Avg", )})
        self.group.update("group1", inputs={"arg1": 42, "arg2": 2})
        self.assertEqual(self.group.compute("group1"), {"m1": t(21.)})

        self.group.remove_group("group1").add_group(
            "group1", ["arg1", "arg2"], {"m1": self.mbi.Avg}
        )
        self.group.update("group1", inputs={"arg1": 42, "arg2": 2})
        self.assertEqual(self.group.compute("group1"), {"m1": t(21.)})

        self.group.remove_group("group1").add_group(
            "group1", ["arg1", "arg2"], {"m1": (self.mbi.Avg, )}
        )
        self.group.update("group1", inputs={"arg1": 42, "arg2": 2})
        self.assertEqual(self.group.compute("group1"), {"m1": t(21.)})

    def test_add_group_spec_init_and_mapping_only(self):
        self.group.add_group("group1", ["arg1", "arg2"], {"m1": ["Avg", ["arg1.value"]]})
        self.group.update("group1", inputs={"arg1": {"value": 42}, "arg2": None})
        self.assertEqual(self.group.compute("group1"), {"m1": t(42.)})

        self.group.remove_group("group1").add_group(
            "group1",
            ["arg1", "arg2"],
            {"m1": ["Avg", {
                "value": "arg1.value",
                "num": "arg1.num"
            }]},
        )
        self.group.update(
            "group1", inputs={
                "arg1": {
                    "value": t(42.),
                    "num": t(2.),
                },
                "arg2": None
            }
        )
        self.assertEqual(self.group.compute("group1"), {"m1": t(21.)})

    def test_update_overload(self):
        self.group.update("group1", a=42, b=2, spec={"m": "Avg"})
        self.group.update("group1", a=42, b=2)
        self.assertEqual(self.group.compute("group1"), {"m": t(21.)})

        self.group.remove_group("group1").update("group1", b=42, a=2, spec={"m": "Avg"})
        self.group.update("group1", b=42, a=2)
        self.assertEqual(self.group.compute("group1"), {"m": t(21.)})

        self.group.remove_group("group1").update("group1", b=42, a=2, spec={"m": "Avg"})
        self.group.update("group1", b=2, a=42)
        self.assertEqual(self.group.compute("group1"), {"m": t(1.)})

        self.group.remove_group("group1").update(
            "group1", inputs=dict(a=42, b=2), spec={"m": "Avg"}
        )
        self.group.update("group1", a=42, b=2)
        self.assertEqual(self.group.compute("group1"), {"m": t(21.)})

    def test_compute_all(self):
        self.group.add_group("group1", ["a"], {"m": "Avg"}).add_group("group2", ["a"], {"m": "Avg"})
        self.group.update('group1', a=42).update('group2', a=42)
        self.assertEqual(
            self.group.compute(), {
                'group1': {
                    'm': t(42.)
                },
                'group2': {
                    'm': t(42.),
                }
            }
        )

    def test_reset_iter(self):
        self.group.update(
            'group1', a=1, spec={
                'm1': ['Avg', ..., 'iter'],
                'm2': ['Avg', ..., 'epoch']
            }
        )
        self.group.reset_iter()
        self.group.update('group1', a=2)
        self.assertEqual(
            self.group.compute('group1'),
            {
                'm1': t(2.),
                'm2': t(1.5)
            },
        )

    def test_reset_epoch(self):
        self.group.update(
            'group1', a=1, spec={
                'm1': ['Avg', ..., 'iter'],
                'm2': ['Avg', ..., 'epoch']
            }
        )
        self.group.reset_epoch()
        self.group.update('group1', a=2)
        self.assertEqual(
            self.group.compute('group1'),
            {
                'm1': t(1.5),
                'm2': t(2.),
            },
        )

    def test_reset_all(self):
        self.group.update(
            'group1', a=1, spec={
                'm1': ['Avg', ..., 'iter'],
                'm2': ['Avg', ..., 'epoch']
            }
        )
        self.group.reset()
        self.group.update('group1', a=2)
        self.assertEqual(
            self.group.compute('group1'),
            {
                'm1': t(2.),
                'm2': t(2.),
            },
        )


class TestDefaultMeterGroup(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.group = self.mg.DefaultMeterGroup()

    def test_update_loss(self):
        self.group.update_loss({'main': 1, 'aux': .5, 'ce': .5})
        self.assertEqual(self.group.compute_loss(), {'main': t(1.), 'aux': t(.5), 'ce': t(.5)})

    def test_update_time(self):
        self.group.update_time({'main': 1, 'aux': .5, 'ce': .5})
        self.assertEqual(self.group.compute_time(), {'main': t(1.), 'aux': t(.5), 'ce': t(.5)})

    def test_update_metrics(self):
        from ignite.metrics.confusion_matrix import ConfusionMatrix
        spec = {
            'cm': [
                lambda: ConfusionMatrix(3),
                [('o.pred_y', 't.y')],
            ]
        }
        pred_y = torch.rand(2, 3, 5, 5)
        y = torch.randint(3, (2, 5, 5))
        indices = pred_y.argmax(dim=1).flatten() + 3 * y.flatten()
        cm = torch.bincount(indices, minlength=3 ** 2).reshape(3, 3)

        self.group.update_metrics({'pred_y': pred_y}, {'y': y}, spec=spec)
        self.assertEqual(self.group.compute_metrics(), {'cm': cm})
