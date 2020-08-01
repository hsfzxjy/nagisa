import unittest

import torch
import numpy as np

from nagisa.torch.meter.meter_builtins import Accumulation, Avg
from nagisa.torch.misc.test import TorchTestCase

t = torch.tensor
a = np.array


class TestAccumulation(TorchTestCase):
    def setUp(self):
        self.accum = Accumulation()

    def test_scalar(self):
        self.accum.update(42.)
        self.assertEqual(self.accum.compute(), [42., 1])
        self.accum.update(t(42.))
        self.assertEqual(self.accum.compute(), [42. * 2, 2])
        self.accum.update(a(42.))
        self.assertEqual(self.accum.compute(), [42. * 3, 3])

    def test_torch_scalar(self):
        self.accum.update(t(42.))
        self.assertEqual(self.accum.compute(), [t(42.), 1])
        self.accum.update(42.)
        self.assertEqual(self.accum.compute(), [t(42.) * 2, 2])
        self.accum.update(a(42.))
        self.assertEqual(self.accum.compute(), [t(42.) * 3, 3])

    def test_numpy_scalar(self):
        self.accum.update(a(42.))
        self.assertEqual(self.accum.compute(), [a(42.), 1])
        self.accum.update(42.)
        self.assertEqual(self.accum.compute(), [a(42.) * 2, 2])
        self.accum.update(t(42.))
        self.assertEqual(self.accum.compute(), [a(42.) * 3, 3])

    def test_scalar_with_num(self):
        self.accum.update(42., 2)
        self.assertEqual(self.accum.compute(), [42., 2])

    def test_torch_1d(self):
        self.accum.update(t([42., 42.]))
        self.assertEqual(self.accum.compute(), [t([42., 42.]), 1])
        self.accum.update(42.)
        self.assertEqual(self.accum.compute(), [t([42., 42.]) * 2, 2])
        self.accum.update(a(42.))
        self.assertEqual(self.accum.compute(), [t([42., 42.]) * 3, 3])

    def test_numpy_1d(self):
        self.accum.update(a([42., 42.]))
        self.assertEqual(self.accum.compute(), [a([42., 42.]), 1])
        self.accum.update(42.)
        self.assertEqual(self.accum.compute(), [a([42., 42.]) * 2, 2])
        self.accum.update(t(42.))
        self.assertEqual(self.accum.compute(), [a([42., 42.]) * 3, 3])

    def test_numpy_1d_with_num(self):
        self.accum.update(a([42., 42.]), num=2)
        self.assertEqual(self.accum.compute(), [a([42., 42.]), 2])

    def test_torch_nd(self):
        self.accum.update(t([[42.], [42.]]))
        self.assertEqual(self.accum.compute(), [t([42. * 2]), 2])
        self.accum.update(a([[42.], [42.], [42.]]))
        self.assertEqual(self.accum.compute(), [t([42. * 5]), 5])

    def test_numpy_nd(self):
        self.accum.update(a([[42.], [42.]]))
        self.assertEqual(self.accum.compute(), [a([42. * 2]), 2])
        self.accum.update(t([[42.], [42.], [42.]]))
        self.assertEqual(self.accum.compute(), [a([42. * 5]), 5])

    def test_torch_nd_with_num(self):
        self.accum.update(t([[42.], [42.]]), num=1)
        self.assertEqual(self.accum.compute(), [t([[42.], [42.]]), 1])

    def test_numpy_nd_with_num(self):
        self.accum.update(a([[42.], [42.]]), num=1)
        self.assertEqual(self.accum.compute(), [a([[42.], [42.]]), 1])

    def test_reset(self):
        self.accum.update(a([[42.], [42.]]), num=1)
        self.accum.reset()
        self.assertEqual(self.accum.compute(), [0.0, 0])


class TestAvg(TorchTestCase):
    def setUp(self):
        self.avg = Avg()

    def test_basic(self):
        self.avg.update(t(42.))
        self.avg.update(a(42.), num=2)
        self.assertEqual(self.avg.compute(), t(42. * 2 / 3))

    def test_empty(self):
        self.assertRaises(ValueError, self.avg.compute)
