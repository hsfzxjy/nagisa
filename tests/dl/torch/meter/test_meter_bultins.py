import functools
import unittest

import torch
import numpy as np
import torch.distributed as dist

from nagisa.dl.torch.misc.testing import TorchTestCase
from nagisa.dl.torch.meter.meter_builtins import Accumulation, Avg

t = torch.tensor
a = functools.partial(np.array, dtype=np.float32)


class TestAccumulation(TorchTestCase):
    def setUp(self):
        self.accum = Accumulation()

        from nagisa.dl.torch.misc.testing import mp_call
        self.mp_call = mp_call

    def test_scalar(self):
        self.accum.update(42.)
        self.assertEqual(self.accum.compute(), [t(42.), 1])
        self.accum.update(t(42.))
        self.assertEqual(self.accum.compute(), [t(42.) * 2, 2])
        self.accum.update(a(42.))
        self.assertEqual(self.accum.compute(), [t(42.) * 3, 3])

    def test_torch_scalar(self):
        self.accum.update(t(42.))
        self.assertEqual(self.accum.compute(), [t(42.), 1])
        self.accum.update(42.)
        self.assertEqual(self.accum.compute(), [t(42.) * 2, 2])
        self.accum.update(a(42.))
        self.assertEqual(self.accum.compute(), [t(42.) * 3, 3])

    def test_numpy_scalar(self):
        self.accum.update(a(42.))
        self.assertEqual(self.accum.compute(), [t(42.), 1])
        self.accum.update(42.)
        self.assertEqual(self.accum.compute(), [t(42. * 2), 2])
        self.accum.update(t(42.))
        self.assertEqual(self.accum.compute(), [t(42. * 3), 3])

    def test_scalar_with_num(self):
        self.accum.update(42., 2)
        self.assertEqual(self.accum.compute(), [t(42.), 2])

    def test_torch_1d(self):
        self.accum.update(t([42., 42.]))
        self.assertEqual(self.accum.compute(), [t([42., 42.]), 1])
        self.accum.update(42.)
        self.assertEqual(self.accum.compute(), [t([42., 42.]) * 2, 2])
        self.accum.update(a(42.))
        self.assertEqual(self.accum.compute(), [t([42., 42.]) * 3, 3])

    def test_numpy_1d(self):
        self.accum.update(a([42., 42.]))
        self.assertEqual(self.accum.compute(), [t([42., 42.]), 1])
        self.accum.update(42.)
        self.assertEqual(self.accum.compute(), [t([42., 42.]) * 2, 2])
        self.accum.update(t(42.))
        self.assertEqual(self.accum.compute(), [t([42., 42.]) * 3, 3])

    def test_numpy_1d_with_num(self):
        self.accum.update(a([42., 42.]), num=2)
        self.assertEqual(self.accum.compute(), [t([42., 42.]), 2])

    def test_torch_nd(self):
        self.accum.update(t([[42.], [42.]]))
        self.assertEqual(self.accum.compute(), [t([42. * 2]), 2])
        self.accum.update(a([[42.], [42.], [42.]]))
        self.assertEqual(self.accum.compute(), [t([42. * 5]), 5])

    def test_numpy_nd(self):
        self.accum.update(a([[42.], [42.]]))
        self.assertEqual(self.accum.compute(), [t([42. * 2]), 2])
        self.accum.update(t([[42.], [42.], [42.]]))
        self.assertEqual(self.accum.compute(), [t([42. * 5]), 5])

    def test_torch_nd_with_num(self):
        self.accum.update(t([[42.], [42.]]), num=1)
        self.assertEqual(self.accum.compute(), [t([[42.], [42.]]), 1])

    def test_numpy_nd_with_num(self):
        self.accum.update(a([[42.], [42.]]), num=1)
        self.assertEqual(self.accum.compute(), [t([[42.], [42.]]), 1])

    def test_reset(self):
        self.accum.update(a([[42.], [42.]]), num=1)
        self.accum.reset()
        self.assertEqual(self.accum.compute(), [0.0, 0])

    @staticmethod
    def main_test_distributed(Q, rank, size):
        accum = Accumulation()
        accum.update(rank)
        Q.put(accum.compute())

    def test_distributed(self):
        result = self.mp_call(self.main_test_distributed, size=4)
        self.assertEqual(result, [[t(6.), 4]] * 4)


class TestAvg(TorchTestCase):
    def setUp(self):
        self.avg = Avg()

        from nagisa.dl.torch.misc.testing import mp_call
        self.mp_call = mp_call

    def test_basic(self):
        self.avg.update(t(42.))
        self.avg.update(a(42.), num=2)
        self.assertEqual(self.avg.compute(), t(42. * 2 / 3))

    def test_empty(self):
        self.assertRaises(ValueError, self.avg.compute)

    @staticmethod
    def main_test_distributed(Q, rank, size):
        avg = Avg()
        avg.update(rank)
        Q.put(avg.compute())

    def test_distributed(self):
        result = self.mp_call(self.main_test_distributed, size=4)
        self.assertEqual(result, [t(1.5)] * 4)
