import logging

logger = logging.getLogger(__name__)

try:
    from tqdm import tqdm
except ModuleNotFoundError:
    logger.warn("`tqdm` not found, progress bar disabled")

    class tqdm:
        def f(self, *args, **kwargs):
            ...

        __init__ = update = f

        del f
