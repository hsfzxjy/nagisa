from collections.abc import Iterable

from nagisa.torch.misc import numeric_typing as nt
from .meter_base import MeterBase, reinit__is_reduced, sync_all_reduce


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
        value_type = nt.type_of(value, raise_exc=True)

        if num is None:
            value_shape = nt.shape_of(value)
            should_accumulate = len(value_shape) > 1
            num = value_shape[0] if should_accumulate else 1
        else:
            num = int(num)
            should_accumulate = False

        if should_accumulate:
            assert isinstance(value, Iterable)
            value = value.sum(**{nt.axis_kw(value_type): 0})

        if not self.n_instances:
            self.sum = nt.as_float(nt.detach(value))
        else:
            self.sum += nt.cast_as(value, self.sum)

        self.n_instances += num

    @sync_all_reduce("sum", "n_instances")
    def compute(self):
        return [self.sum, self.n_instances]


class Avg(Accumulation, key=("builtin.Avg", "Avg")):
    def compute(self):
        if self.n_instances == 0:
            raise ValueError  # TODO
        return self.sum / self.n_instances
