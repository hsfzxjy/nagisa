import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import yaml
except ModuleNotFoundError:
    logger.warn("Library `PyYAML` not found.")

from nagisa.core.misc.io import resolve_until_exists

BASE_KEY = "_BASE_"

# Adapted from: https://github.com/facebookresearch/fvcore/blob/master/fvcore/common/config.py
def load_yaml_with_base(
    filename: str, allow_unsafe: bool = False, caller_level: int = -3
) -> None:
    """
    Just like `yaml.load(open(filename))`, but inherit attributes from its
        `_BASE_`.
    Args:
        filename (str): the file name of the current config. Will be used to
            find the base config file.
        allow_unsafe (bool): whether to allow loading the config file with
            `yaml.unsafe_load`.
    Returns:
        (dict): the loaded yaml
    """
    fn = resolve_until_exists(filename, caller_level=caller_level)
    if filename is None:
        raise ValueError(f"Cannot resolve path {filename!r} into an existing file.")

    try:
        with fn.open("r") as f:
            cfg = yaml.safe_load(f)
    except yaml.constructor.ConstructorError:
        if not allow_unsafe:
            raise
        logger.warning(
            "Loading config {} with yaml.unsafe_load. Your machine may "
            "be at risk if the file contains malicious content.".format(filename)
        )
        f.close()
        with fn.open("r") as f:
            cfg = yaml.unsafe_load(f)  # pyre-ignore

    def merge_a_into_b(a, b):
        # merge dict a into dict b. values in a will overwrite b.
        for k, v in a.items():
            if isinstance(v, dict) and k in b:
                assert isinstance(
                    b[k], dict
                ), "Cannot inherit key '{}' from base!".format(k)
                merge_a_into_b(v, b[k])
            else:
                b[k] = v

    if BASE_KEY in cfg:
        base_cfg_file = Path(cfg[BASE_KEY]).expanduser()
        if not base_cfg_file.is_absolute():
            # the path to base cfg is relative to the config file itself.
            base_cfg_file = fn.parent / base_cfg_file
        base_cfg = load_yaml_with_base(
            str(base_cfg_file), allow_unsafe=allow_unsafe, caller_level=caller_level - 1
        )
        del cfg[BASE_KEY]

        merge_a_into_b(cfg, base_cfg)
        return base_cfg
    return cfg

