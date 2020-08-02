import unittest

import torch
import numpy as np


class TorchTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.addTypeEqualityFunc(torch.Tensor, "assertTensorEqual")
        self.addTypeEqualityFunc(np.ndarray, "assertArrayEqual")

    def assertTensorEqual(self, t1: torch.Tensor, t2: torch.Tensor, msg=None):
        self.assertIsInstance(t1, torch.Tensor, "First argument is not a Tensor")
        self.assertIsInstance(t2, torch.Tensor, "Second argument is not a Tensor")

        standardMsg = ""
        if t1.device != t2.device:
            standardMsg += f"Device {t1.device} != {t2.device}\n"
        elif t1.size() != t2.size():
            standardMsg += f"Tensor shape {t1.size()} != {t2.size()}\n"
        elif (t1 != t2).any():
            standardMsg += f"Tensor {t1} != {t2}\n"
        else:
            return

        self.fail(self._formatMessage(msg, standardMsg))

    def assertArrayEqual(self, t1, t2, msg=None):
        self.assertIsInstance(t1, np.ndarray, "First argument is not numpy.ndarray")
        self.assertIsInstance(t2, np.ndarray, "Second argument is not numpy.ndarray")

        standardMsg = ""
        if t1.shape != t2.shape:
            standardMsg += f"Tensor shape {t1.shape} != {t2.shape}\n"
        elif not (t1 == t2).all():
            standardMsg += f"Tensor {t1} != {t2}\n"
        else:
            return

        self.fail(self._formatMessage(msg, standardMsg))

    def assertEqual(self, x, y, msg=None):
        if isinstance(x, dict) and isinstance(y, dict):
            self.assertSetEqual(set(x), set(y))
            for key in x:
                self.assertEqual(x[key], y[key], msg)
        elif isinstance(x, (list, tuple)) and type(x) is type(y):
            self.assertEqual(len(x), len(y))
            for x_item, y_item in zip(x, y):
                self.assertEqual(x_item, y_item, msg)
        elif torch.Tensor in map(type, (x, y)):
            self.assertIs(type(x), type(y))
            super().assertEqual(x, y, msg)
        else:
            super().assertEqual(x, y, msg)
