import os
import re
import sys
import errno
import shutil
import pathlib
import hashlib
import zipfile
import tempfile
import warnings
import http.cookiejar
import urllib.request
from urllib.parse import urlparse, quote

import torch.hub
from tqdm import tqdm

from nagisa.io.path import resolve_until_exists
from nagisa.misc.registry import FunctionSelector

URLOpener = FunctionSelector(
    f"{__name__}.URLOpener", func_spec=["url | u"], cond_spec=["url | u?"]
)

_google_drive_regexp = re.compile(
    r"^https://drive\.google\.com/(file/d/(?P<id>[\w\-_]+)/view|uc\?.*id=(?P<id2>[^&]+)).*$"
)
_google_drive_confirm_regexp = re.compile(rb"confirm=([\w\d_\-]+)")


@URLOpener.r(lambda url: _google_drive_regexp.match(url) is not None)
def google_drive_opener(url):
    matched = _google_drive_regexp.match(url)
    id = matched.group("id") or matched.group("id2")
    url = f"https://drive.google.com/uc?id={id}"

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    response = opener.open(url)
    content_type = response.getheader("Content-Type")
    if content_type is None:
        raise RuntimeError("Bad response: cannot read content-type.")

    if "text/html" in content_type:
        confirm_code = _google_drive_confirm_regexp.findall(response.read())
        if not confirm_code:
            raise RuntimeError("Cannot obtain confirm code.")
        confirm_code = confirm_code[0].decode("UTF-8")

        return opener.open(f"{url}&confirm={confirm_code}")
    else:
        return response


@URLOpener.r(lambda: True)
def default_opener(url):
    return urllib.request.urlopen(url)


def download_url_to_file(url, dst, hash_prefix=None, progress=True):
    file_size = None
    # We use a different API for python2 since urllib(2) doesn't recognize the CA
    # certificates in older Python
    u = URLOpener.select(url)(url)
    meta = u.info()
    if hasattr(meta, "getheaders"):
        content_length = meta.getheaders("Content-Length")
    else:
        content_length = meta.get_all("Content-Length")
    if content_length is not None and len(content_length) > 0:
        file_size = int(content_length[0])

    # We deliberately save it in a temp file and move it after
    # download is complete. This prevents a local working checkpoint
    # being overridden by a broken download.
    dst = os.path.expanduser(dst)
    dst_dir = os.path.dirname(dst)
    f = tempfile.NamedTemporaryFile(delete=False, dir=dst_dir)

    try:
        if hash_prefix is not None:
            sha256 = hashlib.sha256()
        with tqdm(
            total=file_size,
            disable=not progress,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            while True:
                buffer = u.read(8192)
                if len(buffer) == 0:
                    break
                f.write(buffer)
                if hash_prefix is not None:
                    sha256.update(buffer)
                pbar.update(len(buffer))

        f.close()
        if hash_prefix is not None:
            digest = sha256.hexdigest()
            if digest[: len(hash_prefix)] != hash_prefix:
                raise RuntimeError(
                    'invalid hash value (expected "{}", got "{}")'.format(
                        hash_prefix, digest
                    )
                )
        shutil.move(f.name, dst)
    finally:
        f.close()
        if os.path.exists(f.name):
            os.remove(f.name)

    return dst


def prepare_resource(src, dst, progress=True, check_hash=False):
    if os.path.isfile(src):
        return src

    url = src
    filename = quote(url, safe="")

    if os.path.isdir(dst):
        dst = os.path.join(dst, filename)

    if not os.path.exists(dst):
        sys.stderr.write('Downloading: "{}" to {}\n'.format(url, dst))

        if isinstance(check_hash, str):
            hash_prefix = check_hash
        else:
            hash_prefix = (
                torch.hub.HASH_REGEX.search(filename).group(1) if check_hash else None
            )

        download_url_to_file(url, dst, hash_prefix, progress=progress)

    return dst


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
