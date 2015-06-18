from contextlib import suppress
import random


def weighted_choice(choices):
    # http://stackoverflow.com/a/3679747/547223
    choices = list(choices)
    total = sum(w for c, w in choices)
    r = random.uniform(0, total)
    upto = 0
    for c, w in choices:
        if upto + w > r:
            return c
        upto += w

    assert False, "Shouldn't get here"


def take(n, iterator):
    with suppress(StopIteration):
        for i in range(n):
            yield next(iterator)
