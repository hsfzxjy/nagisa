from argparse import Namespace


class HashableNamespace(Namespace):
    def __hash__(self):
        return hash(((k, v) for k, v in vars(self)))

