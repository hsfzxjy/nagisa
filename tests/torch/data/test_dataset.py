import sys
import unittest


class BaseDatasetTestCase(unittest.TestCase):
    def setUp(self):
        for n in list(filter(lambda x: x.startswith("nagisa.torch.data"), sys.modules)):
            del sys.modules[n]

        from nagisa.torch.data import shortcuts

        self.s = shortcuts


class TestGetDataset(BaseDatasetTestCase):
    def test_get_dataset(self):
        s = self.s

        s.item_keys.set(["img"])

        @s.Resource.r
        @s.Resource.when(lambda m: m.split == "train")
        def id_list():
            return list(range(200))

        @s.Resource.r
        @s.Resource.when(lambda m: m.split == "val")
        def id_list():
            return list(range(100))

        @s.Resource.r
        def img_name(cfg, meta, id):
            return f"/path/{meta.name}/{meta.split}/img_{id}.png"

        from collections import namedtuple

        Image = namedtuple("Image", ["fn"])

        @s.Item.r
        def img(id, img_name):
            return Image(img_name)

        ds = s.get_dataset("dataset1", "train")
        expected = [
            {"img": Image(f"/path/dataset1/train/img_{x}.png")} for x in range(200)
        ]
        self.assertEqual(list(ds), expected)

        ds = s.get_dataset("dataset2", "val")
        expected = [
            {"img": Image(f"/path/dataset2/val/img_{x}.png")} for x in range(100)
        ]
        self.assertEqual(list(ds), expected)

