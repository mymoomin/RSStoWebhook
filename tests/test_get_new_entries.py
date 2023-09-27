from dataclasses import dataclass
from typing import Literal

import pytest

from rss_to_webhook.db_types import Comic
from rss_to_webhook.worker import get_new_entries


@pytest.fixture()
def comic() -> Comic:
    return Comic(
        name="Test Webcomic",
        url="https://example.com/rss",
        hash=b"\xa9\x0c\x16\xe5\xe2\x8c6\xdd\x01}K\x85\x1fn\x8e\xd2",
        last_entries=["https://example.com/page/0"],
    )


@dataclass(slots=True)
class Feed:
    bozo: Literal[False, 1]
    encoding: str
    entries: list
    feed: dict
    version: str


@pytest.fixture()
def feed():
    return Feed(
        bozo=False,
        encoding="utf-8",
        version="rss20",
        feed={"title": "Test Webcomic"},
        entries=[{"link": "https://example.com/page/0"}],
    )


def test_happy_path(comic, feed):
    """
    This is just the normal usage.

    Test asserts that `get_new_entries` functions when nothing has changed
    since the last check
    """
    new_entries = get_new_entries(comic, feed, None)
    assert new_entries == ([], True)
