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
    """
    This is just the normal usage.

    Test asserts that `make_body` functions on the happy path.
    """
    entry: Entry = {"link": "https://example.com/page/1", "title": "Page 1!"}
    body = make_body(comic, entry)
    assert body == {
        "embeds": [
            {
                "color": 0x5C64F4,
                "title": "**Page 1!**",
                "url": "https://example.com/page/1",
                "description": "New Test Webcomic!",
            },
        ],
    }


def test_bad_url_scheme(comic):
    """
    This is a regression test for
    [13a7171](https://github.com/mymoomin/RSStoWebhook/commit/13a7171be8f19164902a36e1f5abd587f852a303),
    where a bad url scheme caused the service to fail for multiple days.

    Test asserts that `make_body` will correct bad url schemes.
    """
    entry: Entry = {"link": "hps://example.com/page/1", "title": "Page 1!"}
    body = make_body(comic, entry)
    assert body == {
        "embeds": [
            {
                "color": 0x5C64F4,
                "title": "**Page 1!**",
                "url": "https://example.com/page/1",
                "description": "New Test Webcomic!",
            },
        ],
    }


def test_no_title(comic):
    """
    This is a regression test for
    [0249766](https://github.com/mymoomin/RSStoWebhook/commit/0249766c715879891e3d21bb61bc537839020f5b),
    where a missing entry title caused the embed to not have a title.

    Test asserts that even without a title the embed has a title.
    """
    entry: Entry = {"link": "hps://example.com/page/1"}
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
