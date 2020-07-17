import re
import os
import sys
import shutil
import pathlib
import logging
import hashlib
import tempfile
import traceback
import warnings
import http.cookiejar
import urllib.request
from typing import Optional
from urllib.parse import urlparse, quote

from nagisa.core.misc.registry import FunctionSelector
from nagisa.core.misc.progressbar import tqdm


__all__ = [
    "resolve_until_exists",
    "URLOpener",
    "download_url_to_file",
    "prepare_resource",
]

logger = logging.Logger(__name__)


def resolve_until_exists(
    path: str, *, caller_level: int = -3
) -> Optional[pathlib.Path]:
    assert caller_level < 0

    path = pathlib.Path(path)

    if not path.is_absolute():
        tb_list = traceback.extract_stack(limit=abs(caller_level))
        if len(tb_list) < abs(caller_level):
            raise ValueError(
                "Caller level {} is too deep for current context.".format(caller_level)
            )
        caller_filename = pathlib.Path(tb_list[caller_level].filename)
        if pathlib.Path(caller_filename).is_file():
            path = pathlib.Path(caller_filename).parent / path
        else:
            logger.warn(
                "{} is not a valid file. Use CWD as relative instead.".format(
                    caller_filename
                )
            )
            path = pathlib.Path.cwd() / path

    return path if path.exists() else None


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

