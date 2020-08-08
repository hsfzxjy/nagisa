import sys
import torch

from nagisa.dl.torch.misc.testing import TorchTestCase


class BaseDatasetTestCase(TorchTestCase):
    def setUp(self):
        for n in list(filter(lambda x: x.startswith("nagisa.dl.torch"), sys.modules)):
            del sys.modules[n]

        from nagisa.dl.torch import data as s

        self.s = s

        @s.Resource.r
        def id_list():
            return list(range(100))

        @s.Item.r("item1")
        @s.Item.r("item2")
        @s.Item.r("item3")
        def item1(id):
            return id

        s.item_keys.set(["item1", "item2", "item3"])
        self.dataset = s.get_dataset("", "", cfg="mock")



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
        loader = s.DataLoader("mock", self.dataset, batch_size=4)
        self.assertListEqual(list(loader), expected)

    def test_dataloader_torch_default_collate(self):
        s = self.s

        @s.Collate.r
        def item2(cfg, items):
            return torch.tensor(items).unsqueeze(-1)

        expected = []
        chunk_size = 4
        for i in range(0, 100, chunk_size):
            items = torch.tensor([i + j for j in range(chunk_size)])
            expected.append({
                "item1": items,
                "item2": items.unsqueeze(-1),
                "item3": items,
            })
        loader = s.DataLoader("mock", self.dataset, batch_size=4)
        self.assertListEqual(list(loader), expected)

    def test_dataset_as_loader(self):
        expected = []
        chunk_size = 4
        for i in range(0, 100, chunk_size):
            items = torch.tensor([i + j for j in range(chunk_size)])
            expected.append({
                "item1": items,
                "item2": items,
                "item3": items,
            })

        self.assertListEqual(list(self.dataset.as_loader(batch_size=4)), expected)
