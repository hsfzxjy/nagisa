import unittest

import torch


class TorchTestCase(unittest.TestCase):
    def assertTensorEqual(self, t1: torch.Tensor, t2: torch.Tensor, msg=None):
        self.assertIsInstance(t1, torch.Tensor, "First argument is not a Tensor")
        self.assertIsInstance(t2, torch.Tensor, "Second argument is not a Tensor")

        standardMsg = ""
        if t1.device != t2.device:
            standardMsg += f"Device {t1.device} != {t2.device}\n"
        elif t1.size() != t2.size():
            standardMsg += f"Tensor shape {t1.size()} != {t2.size()}\n"
        elif (t1 - t2).abs().sum().item() != 0:
            standardMsg += f"Tensor {t1} != {t2}\n"
        else:
            return

        self.fail(self._formatMessage(msg, standardMsg))

