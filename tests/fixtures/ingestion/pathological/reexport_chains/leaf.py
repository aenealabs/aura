"""Leaf of a re-export chain. Defines the actual entities."""


class Helper:
    def do(self):
        return 1


def helper_fn():
    return Helper().do()
