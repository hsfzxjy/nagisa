from collections.abc import Iterable

from nagisa.dl.torch.misc import casting
from .meter_base import MeterBase, reinit__is_reduced, sync_all_reduce


# pylint: disable=attribute-defined-outside-init
class Accumulation(MeterBase, key=()):
    def __init__(self):
        super().__init__()
        self.reset()

    @reinit__is_reduced
    def reset(self):
        self.sum = 0.0
        self.n_instances = 0

    @reinit__is_reduced
    def update(self, value, num=None):
        if self.n_instances:
            value = casting.as_(value, self.sum)
        else:
            value = casting.to_tensor(value)

        if num is None:
            value_shape = value.size()
            should_accumulate = len(value_shape) > 1
            num = value_shape[0] if should_accumulate else 1
        else:
            num = int(num)
            should_accumulate = False

        if should_accumulate:
            assert isinstance(value, Iterable)
            value = value.sum(dim=0)

        if not self.n_instances:
            self.sum = value.float()
        else:
            self.sum += value

        self.n_instances += num

    @sync_all_reduce("sum", "n_instances")
    def compute(self):
        return [self.sum, self.n_instances]


class Avg(Accumulation, key=("builtin.Avg", "Avg")):
    @sync_all_reduce("sum", "n_instances")
    def compute(self):
        if self.n_instances == 0:
            raise ValueError("`Avg.compute()` should be called after at least one example updated")
        return self.sum / self.n_instances
