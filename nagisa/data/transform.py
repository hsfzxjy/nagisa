from nagisa.misc.cache import Cache
from nagisa.misc.naming import camel_to_snake
from nagisa.core.state.scheme import SchemeNode
from nagisa.core.state.config import ConfigValue, ConfigNode

from ._registries import Transform

__all__ = [
    "trans_seq",
    "trans_kwargs",
    "BaseTransform",
    "apply_transform",
]

trans_seq = ConfigValue(
    f"{__name__}.trans_seq", func_spec=["cfg|c?", "meta|m?"], default=lambda: []
)
trans_kwargs = ConfigValue(
    f"{__name__}.trans_kwargs", func_spec=["cfg|c?", "meta|m?"], default=lambda: {}
)


class BaseTransform(object):
    @SchemeNode.writable
    class _kwargs_template:
        pass

    def __init_subclass__(cls, key=None):
        if key is None:
            key = camel_to_snake(cls.__name__)

        Transform.register(key, cls)

    def __init__(self, *, cfg=None, meta=None, **kwargs):
        self.__cfg = cfg
        self.meta = meta
        kwargs = SchemeNode.from_class(self._kwargs_template)().merge_from_dict(kwargs)
        self._check_kwargs(kwargs)
        self.kwargs = kwargs.finalize()

    def _check_kwargs(self, kwargs):
        pass

    @property
    def cfg(self):
        if self.__cfg is not None:
            return self.__cfg
        return ConfigNode.instance(raise_exc=True)

    def _use_me(self, item_dict):
        return True

    def _setup(self, item_dict):
        pass

    def _default(self, item, item_key, item_dict):
        return item

    def __call__(self, item_dict):
        self._setup(item_dict)

        if not self._use_me(item_dict):
            return item_dict

        ret_item_dict = {}
        for item_key, item in item_dict.items():
            func_name = f"_t_{item_key}"

            if hasattr(self, func_name):
                item = getattr(self, func_name)(item, item_dict)
            else:
                item = self._default(item, item_key, item_dict)

            ret_item_dict[item_key] = item

        return ret_item_dict


__cache = Cache()


def apply_transform(cfg, meta, item_dict):
    trans_seq_list = trans_seq.func(cfg=cfg, meta=meta)
    cache_key = (meta, *trans_seq_list)

    transforms = __cache.get(cache_key)
    if transforms is __cache.Null:

        trans_kwargs_mapping = trans_kwargs.value(cfg=cfg, meta=meta)
        if isinstance(trans_kwargs_mapping, ConfigNode):
            trans_kwargs_mapping = trans_kwargs_mapping.value_dict()

        transforms = []
        for trans_key in trans_seq_list:
            if trans_key in trans_kwargs_mapping:
                kwargs = trans_kwargs_mapping[trans_key]
            else:
                kwargs = {}

            transforms.append(Transform[trans_key](cfg=cfg, meta=meta, **kwargs))

        __cache.set(cache_key, transforms)

    for transform in transforms:
        item_dict = transform(item_dict)

    return item_dict

