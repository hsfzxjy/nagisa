import inspect
import collections
from torch.utils.data.dataset import Dataset as torch_Dataset

from nagisa.core.state.config import ConfigNode, ConfigValue

from ._data_resolver import DataResolver
from .transform import apply_transform
from .dataloader import DataLoader

__all__ = [
    "item_keys",
    "Dataset",
    "get_dataset",
]

item_keys = ConfigValue(f"{__name__}.item_keys", is_func=True)

DatasetMeta = collections.namedtuple("DatasetMeta", ("name", "split"))


class Dataset(torch_Dataset):
    def __init__(self, cfg, name, split):
        self.cfg = cfg
        self.meta = DatasetMeta(name=name, split=split)
        self.data_resolver = DataResolver(cfg, self.meta)
        self.id_list = self.data_resolver.get_id_list()

    def __len__(self):
        return len(self.id_list)

    def __getitem__(self, index):
        id = self.id_list[index]

        items_dict = {}
        for item_key in item_keys.value(self.cfg, self.meta):
            items_dict[item_key] = self.data_resolver.get_item(id, item_key)

        apply_transform(self.cfg, self.meta, items_dict)

        return items_dict

    def as_loader(self, *args, **kwargs):
        return DataLoader(self.cfg, self, *args, **kwargs)


def get_dataset(name, split, cfg=None):
    if cfg is None:
        cfg = ConfigNode.instance(raise_exc=True)

    return Dataset(cfg, name, split)
