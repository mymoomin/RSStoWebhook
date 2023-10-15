"""Utility functions.

This file is only for things that should be in the standard library, or that
are in the standard library in future versions.

More specific functionality should go in more specific files.
"""

from collections.abc import Generator, Sequence
from itertools import islice
from typing import TypeVar

_T_co = TypeVar("_T_co", covariant=True)


def batched(
    iterable: Sequence[_T_co], n: int
) -> Generator[tuple[_T_co, ...], None, None]:
    """Batch data from the iterable into tuples of length at most n.

    The last batch may be shorter than n.

    A reimplementation of [itertools.batched](https://docs.python.org/3.12/library/itertools.html#itertools.batched).
    """
    # batched('ABCDEFG', 3) --> 'ABC' 'DEF' 'G'
    if n < 1:
        raise ValueError("n must be at least one")
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch
