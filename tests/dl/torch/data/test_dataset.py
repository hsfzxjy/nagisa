import unittest

from nagisa.core.misc.testing import ReloadModuleTestCase


class BaseDatasetTestCase(ReloadModuleTestCase):
    drop_modules = [
        '^nagisa.dl.torch',
    ]
    attach = [
        ['data_module', 'nagisa.dl.torch.data'],
    ]


class TestGetDataset(BaseDatasetTestCase):
    def test_get_dataset(self):
        s = self.data_module

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

        ds = s.get_dataset("dataset1", "train", cfg="mock")
        expected = [{"img": Image(f"/path/dataset1/train/img_{x}.png")} for x in range(200)]
        self.assertEqual(list(ds), expected)

        ds = s.get_dataset("dataset2", "val", cfg="mock")
        expected = [{"img": Image(f"/path/dataset2/val/img_{x}.png")} for x in range(100)]
        self.assertEqual(list(ds), expected)
