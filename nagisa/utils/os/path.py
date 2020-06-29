import os
import pathlib
import traceback
import logging
from typing import Optional

logger = logging.Logger(__name__)

__all__ = [
    "resolve_until_exists",
]


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
