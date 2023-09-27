from typing import TYPE_CHECKING

import pytest

from rss_to_webhook.db_types import Comic
from rss_to_webhook.worker import make_body

if TYPE_CHECKING:
    from feedparser.util import Entry


@pytest.fixture()
def comic():
    return Comic(
        name="Test Webcomic",
        url="https://example.com/rss",
        hash=b"\xa9\x0c\x16\xe5\xe2\x8c6\xdd\x01}K\x85\x1fn\x8e\xd2",
        last_entries=["https://example.com/page/0"],
    )


def test_happy_path(comic):
    entry: Entry = {"link": "https://example.com/page/1"}
    body = make_body(comic, entry)
    assert body == {
        "embeds": [
            {
                "color": 0x5C64F4,
                "title": "**Test Webcomic**",
                "url": "https://example.com/page/1",
                "description": "New Test Webcomic!",
            },
        ],
    }
