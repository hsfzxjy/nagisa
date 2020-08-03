import inspect
import collections
from torch.utils.data.dataset import Dataset as torch_Dataset

from nagisa.core.state.config import ConfigNode, ConfigValue, cfg_property

from ._data_resolver import DataResolver
from .transform import apply_transform
from .dataloader import DataLoader

__all__ = [
    "item_keys",
    "Dataset",
    "get_dataset",
]

item_keys = ConfigValue(f"{__name__}.item_keys", func_spec=["cfg|c?", "meta|m?"])

DatasetMeta = collections.namedtuple("DatasetMeta", ("name", "split"))


class Dataset(torch_Dataset):
    def __init__(self, cfg, name, split):
        self._cfg_ = cfg
        self._meta_ = DatasetMeta(name=name, split=split)
        self._data_resolver_ = DataResolver(cfg, self._meta_)
        self._id_list_ = self._data_resolver_.get_id_list()

    cfg = cfg_property

    def __len__(self):
        return len(self._id_list_)

    def __getitem__(self, index):
        id = self._id_list_[index]

        items_dict = {}
        for item_key in item_keys.value(self.cfg, self._meta_):
            items_dict[item_key] = self._data_resolver_.get_item(id, item_key)

        apply_transform(self.cfg, self._meta_, items_dict)

        return items_dict

    def as_loader(self, *args, **kwargs):
        return DataLoader(self.cfg, self, *args, **kwargs)


def get_dataset(name, split, cfg=None):
    return Dataset(cfg, name, split)
