from torch.utils.data import DataLoader as torch_DataLoader
from torch.utils.data.dataloader import default_collate

from ._registries import Collate

__all__ = [
    "DataLoader",
]


class CollateFn:
    def __init__(self, cfg):
        self.cfg = cfg

    def __call__(self, item_dicts):
        assert len(item_dicts) > 0

        ret_dict = {}
        for key in item_dicts[0]:
            items = [item_dict[key] for item_dict in item_dicts]
            f = Collate.select(key, self.cfg)
            if f is not None:
                items = f(self.cfg, key, items)
            else:
                items = default_collate(items)
                f = default_collate
            ret_dict[key] = items

        return ret_dict


class DataLoader(torch_DataLoader):
    def __init__(self, cfg, *args, **kwargs):
        kwargs["collate_fn"] = CollateFn(cfg)
        super().__init__(*args, **kwargs)

