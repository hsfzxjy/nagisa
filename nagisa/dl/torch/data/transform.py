from nagisa.core.misc.cache import Cache
from nagisa.core.misc.naming import camel_to_snake
from nagisa.core.state.scheme import SchemeNode
from nagisa.core.state.config import ConfigValue, ConfigNode, cfg_property

from ._registries import Transform

__all__ = [
    "trans_seq",
    "trans_kwargs",
    "BaseTransform",
    "apply_transform",
]

trans_seq = ConfigValue(
    f"{__name__}.trans_seq",
    func_spec=["cfg|c?", "meta|m?"],
    default=lambda: [],
)
trans_kwargs = ConfigValue(
    f"{__name__}.trans_kwargs",
    func_spec=["cfg|c?", "meta|m?"],
    default=lambda: {},
)


class BaseTransform:
    @SchemeNode.writable
    class _kwargs_scheme_:
        pass

    def __init_subclass__(cls, key=None):
        if key is None:
            key = camel_to_snake(cls.__name__)

        Transform.register(key, cls)

    def __init__(self, *, cfg=None, meta=None, **kwargs):
        self._cfg_ = cfg
        self.meta = meta
        kwargs = SchemeNode.from_class(self._kwargs_scheme_, )().merge_from_dict(kwargs)
        self._check_kwargs_(kwargs)
        self.kwargs = kwargs.finalize()

    def _check_kwargs_(self, kwargs):
        pass

    cfg = cfg_property

    def _use_me_(self, item_dict):
        return True

    def _setup_(self, item_dict):
        pass

    def _default_(self, item, item_key, item_dict):
        return item

    def __call__(self, item_dict):
        self._setup_(item_dict)

        if not self._use_me_(item_dict):
            return item_dict

        ret_item_dict = {}
        for item_key, item in item_dict.items():
            func_name = f"_t_{item_key}_"

            if hasattr(self, func_name):
                item = getattr(self, func_name)(item, item_dict)
            else:
                item = self._default_(item, item_key, item_dict)

            ret_item_dict[item_key] = item

        return ret_item_dict


__cache__ = Cache()


def apply_transform(cfg, meta, item_dict):
    trans_seq_list = trans_seq.func(cfg=cfg, meta=meta)
    cache_key = (meta, *trans_seq_list)

    transforms = __cache__.get(cache_key)
    if transforms is __cache__.Empty:

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

        __cache__.set(cache_key, transforms)

    for transform in transforms:
        item_dict = transform(item_dict)

    return item_dict
