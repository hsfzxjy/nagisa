import sys
import torch
import unittest


class BaseDatasetTestCase(unittest.TestCase):
    def setUp(self):
        for n in list(filter(lambda x: x.startswith("nagisa.data"), sys.modules)):
            del sys.modules[n]

        from nagisa.data import shortcuts as s
        from nagisa.data.dataloader import DataLoader

        self.s = s

        @s.Resource.r
        def id_list(cfg, meta):
            return list(range(100))

        @s.Item.r
        def item1(cfg, meta, id):
            return id

        @s.Item.r
        def item2(cfg, meta, id):
            return id

        @s.Item.r
        def item3(cfg, meta, id):
            return id

        s.item_keys.set(["item1", "item2", "item3"])
        self.dataset = s.get_dataset("", "")

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

    def assertItemsEqual(self, items_seq1, items_seq2):
        self.assertEqual(len(items_seq1), len(items_seq2))

        for items_dict1, items_dict2 in zip(items_seq1, items_seq2):
            self.assertSequenceEqual(items_dict1.keys(), items_dict2.keys())

            for key in items_dict1:
                self.assertTensorEqual(items_dict1[key], items_dict2[key])


class TestDataLoader(BaseDatasetTestCase):
    def test_dataloader(self):
        s = self.s

        @s.Collate.r
        def item2(cfg, items):
            return torch.tensor(items).unsqueeze(-1)

        @s.Collate.r
        def default(cfg, items):
            return torch.tensor(items).unsqueeze(-1).unsqueeze(-1)

        expected = []
        chunk_size = 4
        for i in range(0, 100, chunk_size):
            items = torch.tensor([i + j for j in range(chunk_size)])
            expected.append(
                {
                    "item1": items.unsqueeze(-1).unsqueeze(-1),
                    "item2": items.unsqueeze(-1),
                    "item3": items.unsqueeze(-1).unsqueeze(-1),
                }
            )
        loader = s.DataLoader(None, self.dataset, batch_size=4)
        self.assertItemsEqual(list(loader), expected)

    def test_dataloader_torch_default_collate(self):
        s = self.s

        @s.Collate.r
        def item2(cfg, items):
            return torch.tensor(items).unsqueeze(-1)

        expected = []
        chunk_size = 4
        for i in range(0, 100, chunk_size):
            items = torch.tensor([i + j for j in range(chunk_size)])
            expected.append(
                {"item1": items, "item2": items.unsqueeze(-1), "item3": items,}
            )
        loader = s.DataLoader(None, self.dataset, batch_size=4)
        self.assertItemsEqual(list(loader), expected)

    def test_dataset_as_loader(self):
        expected = []
        chunk_size = 4
        for i in range(0, 100, chunk_size):
            items = torch.tensor([i + j for j in range(chunk_size)])
            expected.append(
                {"item1": items, "item2": items, "item3": items,}
            )

        self.assertItemsEqual(list(self.dataset.as_loader(batch_size=4)), expected)

