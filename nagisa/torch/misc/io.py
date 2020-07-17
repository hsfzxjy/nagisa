import os
import errno
import zipfile
import warnings

import torch
import torch.hub

from nagisa.core.misc.io import prepare_resource


def load_state_dict(
    location,
    model_dir=None,
    map_location=None,
    progress=True,
    check_hash=False,
    return_filename=False,
):
    # Issue warning to move data if old env is set
    if os.getenv("TORCH_MODEL_ZOO"):
        warnings.warn(
            "TORCH_MODEL_ZOO is deprecated, please use env TORCH_HOME instead"
        )

    if model_dir is None:
        torch_home = torch.hub._get_torch_home()
        model_dir = os.path.join(torch_home, "checkpoints")

    try:
        os.makedirs(model_dir)
    except OSError as e:
        if e.errno == errno.EEXIST:
            # Directory already exists, ignore.
            pass
        else:
            # Unexpected OSError, re-raise.
            raise

    cached_file = prepare_resource(
        location, model_dir, progress=progress, check_hash=check_hash
    )
    if zipfile.is_zipfile(cached_file):
        with zipfile.ZipFile(cached_file) as cached_zipfile:
            members = cached_zipfile.infolist()
            if len(members) != 1:
                raise RuntimeError("Only one file(not dir) is allowed in the zipfile")
            cached_zipfile.extractall(model_dir)
            extraced_name = members[0].filename
            cached_file = os.path.join(model_dir, extraced_name)

    loaded = torch.load(cached_file, map_location=map_location)

    if return_filename:
        return loaded, cached_file

    return cached_file
