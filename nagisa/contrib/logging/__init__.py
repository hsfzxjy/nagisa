# Adopted from https://github.com/facebookresearch/detectron2/blob/master/detectron2/utils/logger.py
import os
import sys
import time
import logging
import warnings
import functools
from collections import Counter

try:
    from termcolor import colored
except ImportError:
    warnings.warn('Install `termcolor` to use colorful logging')
    colored = None

from nagisa.core.misc.io import resolve

__all__ = [
    'init_logging',
    'setup_logger',
]


class _ColorfulFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        self._root_name = kwargs.pop("root_name") + "."
        super(_ColorfulFormatter, self).__init__(*args, **kwargs)

    def formatMessage(self, record):
        log = super(_ColorfulFormatter, self).formatMessage(record)
        if colored is None:
            return log
        if record.levelno == logging.WARNING:
            prefix = colored("WARNING", "red", attrs=["blink"])
        elif record.levelno == logging.ERROR or record.levelno == logging.CRITICAL:
            prefix = colored("ERROR", "red", attrs=["blink", "underline"])
        else:
            return log
        return prefix + " " + log


def _find_caller():
    """
    Returns:
        str: module name of the caller
        tuple: a hashable key to be used to identify different callers
    """
    frame = sys._getframe(2)
    while frame is not None:
        code = frame.f_code
        if os.path.join("logging", "__init__.") not in code.co_filename:
            return (code.co_filename, frame.f_lineno, code.co_name)
        frame = frame.f_back


class _Logger(logging.Logger):

    _LOG_COUNTER = Counter()
    _LOG_TIMER = {}

    def log_first_n(
        self,
        msg,
        n=1,
        *,
        lvl=logging.INFO,
        key=("caller", "message"),
    ):
        if isinstance(key, str):
            key = (key, )
        assert len(key) > 0

        caller_key = _find_caller()
        hash_key = ()
        if "caller" in key:
            hash_key = hash_key + caller_key
        if "message" in key:
            hash_key = hash_key + (msg, )

        self._LOG_COUNTER[hash_key] += 1
        if self._LOG_COUNTER[hash_key] <= n:
            self.log(lvl, msg)

    def log_once(
        self,
        msg,
        *,
        lvl=logging.INFO,
        key=("caller", "message"),
    ):
        return self.log_first_n(msg, n=1, lvl=lvl, key=key)

    def log_every_n(self, msg, n=1, *, lvl=logging.INFO):
        key = _find_caller()
        self._LOG_COUNTER[key] += 1
        if n == 1 or self._LOG_COUNTER[key] % n == 1:
            self.log(lvl, msg)

    def log_every_n_seconds(self, msg, n=1, *, lvl=logging.INFO):
        key = _find_caller()
        last_logged = self._LOG_TIMER.get(key, None)
        current_time = time.time()
        if last_logged is None or current_time - last_logged >= n:
            self.log(lvl, msg)
            self._LOG_TIMER[key] = current_time


def init_logging():
    logging.setLoggerClass(_Logger)


def setup_logger(
    output=None,
    distributed_rank=0,
    *,
    color=True,
    name="nagisa",
):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    plain_formatter = logging.Formatter(
        "[%(asctime)s] %(name)s %(levelname)s: %(message)s", datefmt="%m/%d %H:%M:%S"
    )
    # stdout logging: master only
    if distributed_rank == 0:
        ch = logging.StreamHandler(stream=sys.stdout)
        ch.setLevel(logging.DEBUG)
        if color and colored is not None:
            formatter = _ColorfulFormatter(
                colored("[%(asctime)s %(name)s]: ", "green") + "%(message)s",
                datefmt="%m/%d %H:%M:%S",
                root_name=name,
            )
        else:
            formatter = plain_formatter
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    # file logging: all workers
    if output is not None:
        if output.endswith(".txt") or output.endswith(".log"):
            filename = output
        else:
            filename = os.path.join(output, "log.txt")
        if distributed_rank > 0:
            filename = filename + ".rank{}".format(distributed_rank)
        filename = resolve(filename, method='cwd')
        filename.parent.mkdir(exist_ok=True)

        fh = logging.StreamHandler(_cached_log_stream(filename))
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(plain_formatter)
        logger.addHandler(fh)

    return logger


# cache the opened file object, so that different calls to `setup_logger`
# with the same file name can safely write to the same file.
@functools.lru_cache(maxsize=None)
def _cached_log_stream(filename):
    return filename.open(mode='a')
