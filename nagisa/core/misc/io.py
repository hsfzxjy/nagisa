import re
import os
import sys
import math
import shutil
import pathlib
import logging
import hashlib
import tempfile
import warnings
import traceback
import functools
import http.cookiejar
import urllib.request
from urllib.parse import urlparse, quote
from typing import Optional, Union, Callable

from nagisa.core.misc.progressbar import tqdm
from nagisa.core.misc.registry import FunctionSelector

__all__ = [
    "resolve",
    "resolve_until",
    "resolve_until_exists",
    "URLOpener",
    "download_url_to_file",
    "prepare_resource",
]

logger = logging.getLogger(__name__)

NOT_NAGISA = float('inf')


@functools.lru_cache()
def nagisa_root_dir() -> pathlib.Path:
    return pathlib.Path(__file__).absolute().parent.parent.parent


def _resolve_path_based_on_caller(path, caller_level=NOT_NAGISA) -> Optional[pathlib.Path]:
    tb_list = traceback.extract_stack()
    if math.isfinite(caller_level):
        assert isinstance(caller_level, int) and caller_level < 0
        frame = tb_list[caller_level - 1]
        print(frame)
    else:
        root_dir = nagisa_root_dir
        for frame in tb_list[::-1]:
            if not frame.filename.startswith(root_dir):
                break
        else:
            return None

    return pathlib.Path(frame.filename).parent / path


def _resolve_path_based_on_cwd(path) -> pathlib.Path:
    return pathlib.Path.cwd() / path


_DEFAULT_RESOLVING_ORDER = (
    'caller',
    'cwd',
)


def resolve_until(
    path: Union[str, pathlib.Path],
    *,
    condition: Callable = pathlib.Path.exists,
    order: tuple = _DEFAULT_RESOLVING_ORDER,
    caller_level: Union[int, float] = NOT_NAGISA,
) -> Optional[pathlib.Path]:
    path = pathlib.Path(path)

    if not path.is_absolute():
        for method in order:
            if method == 'caller':
                path = _resolve_path_based_on_caller(path, caller_level=caller_level - 1)
            elif method == 'cwd':
                path = _resolve_path_based_on_cwd(path)
            else:
                raise RuntimeError

            if path is not None and condition(path):
                return path

    return path if path is not None and condition(path) else None


def resolve_until_exists(
    path: Union[str, pathlib.Path],
    *,
    order: tuple = _DEFAULT_RESOLVING_ORDER,
    caller_level: Union[int, float] = NOT_NAGISA,
) -> Optional[pathlib.Path]:
    return resolve_until(
        path=path,
        condition=pathlib.Path.exists,
        order=order,
        caller_level=caller_level - 1,
    )


def resolve(
    path: Union[str, pathlib.Path],
    *,
    method: str,
    caller_level: Union[int, float] = NOT_NAGISA,
):
    return resolve_until(
        path,
        order=(method, ),
        condition=lambda _: True,
        caller_level=caller_level - 1,
    )


URLOpener = FunctionSelector(f"{__name__}.URLOpener", func_spec=["url | u"], cond_spec=["url | u?"])

_google_drive_pattern_ = re.compile(
    r"^https://drive\.google\.com/(file/d/(?P<id>[\w\-_]+)/view|uc\?.*id=(?P<id2>[^&]+)).*$"
)
_google_drive_confirm_regexp = re.compile(rb"confirm=([\w\d_\-]+)")


@URLOpener.r(lambda url: _google_drive_pattern_.match(url) is not None)
def google_drive_opener(url):
    matched = _google_drive_pattern_.match(url)
    id = matched.group("id") or matched.group("id2")
    url = f"https://drive.google.com/uc?id={id}"

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    response = opener.open(url)
    content_type = response.getheader("Content-Type")
    if content_type is None:
        raise RuntimeError("Bad response: cannot read content-type")

    if "text/html" in content_type:
        confirm_code = _google_drive_confirm_regexp.findall(response.read())
        if not confirm_code:
            raise RuntimeError("Cannot obtain confirm code")
        confirm_code = confirm_code[0].decode("UTF-8")

        return opener.open(f"{url}&confirm={confirm_code}")
    else:
        return response


@URLOpener.r(lambda: True)
def default_opener(url):
    return urllib.request.urlopen(url)


def download_url_to_file(url, dst, hash_prefix=None, progress=True):
    file_size = None
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
            if digest[:len(hash_prefix)] != hash_prefix:
                raise RuntimeError(f'Invalid hash value (expected {hash_prefix!r}, got {digest!r})')
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
            hash_prefix = (torch.hub.HASH_REGEX.search(filename).group(1) if check_hash else None)

        download_url_to_file(url, dst, hash_prefix, progress=progress)

    return dst
