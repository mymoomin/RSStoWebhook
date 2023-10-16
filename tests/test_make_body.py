from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pytest
from bson import ObjectId

from rss_to_webhook.check_feeds_and_update import _make_messages
from rss_to_webhook.db_types import Comic
from rss_to_webhook.discord_types import Message

if TYPE_CHECKING:
    from feedparser.util import Entry


@pytest.fixture()
def comic() -> Comic:
    return Comic(
        _id=ObjectId("111111111111111111111111"),
        role_id=1,
        dailies=[],
        title="Test Webcomic",
        feed_url="https://example.com/rss",
        feed_hash=b"\xa9\x0c\x16\xe5\xe2\x8c6\xdd\x01}K\x85\x1fn\x8e\xd2",
        last_entries=[{"link": "https://example.com/page/0"}],
    )


def filter_nones(message: Message) -> Message:
    """Remove all `None`s from a `Message`.

    Discord treats message values that are `None` as though they weren't in the
    dictionary at all, so `None` and missing are equivalent. Pytest doesn't.
    This normalises all `None` values to just be missing, to hide the difference.
    """
    return {key: value for key, value in message.items() if value is not None}  # type: ignore [reportGeneralTypeIssues, return-value]
    # This is correctly-typed because every key in `Message` is optional,
    # so removing keys doesn't change the type


def test_happy_path(comic: Comic) -> None:
    """Given a normal entry, the correct message body is returned.

    This is just the normal usage.
    """
    entry: Entry = {"link": "https://example.com/page/1", "title": "Page 1!"}
    body = _make_messages(comic, [entry])[0]
    # The Message() is just for show (underhanded cheats to increase our code coverage)
    assert filter_nones(body) == Message(
        {
            "embeds": [
                {
                    "color": 0x5C64F4,
                    "title": "**Page 1!**",
                    "url": "https://example.com/page/1",
                    "description": "New Test Webcomic!",
                },
            ],
            "content": "<@&1>",
        }
    )


def test_bad_url_scheme(comic: Comic) -> None:
    """Bad url schemes are corrected.

    Regression test for
    [13a7171](https://github.com/mymoomin/RSStoWebhook/commit/13a7171be8f19164902a36e1f5abd587f852a303),
    where a bad url scheme caused the service to fail for multiple days.

    Test asserts that `make_body` will correct bad url schemes.
    """
    entry: Entry = {"link": "hps://example.com/page/1", "title": "Page 1!"}
    body = _make_messages(comic, [entry])[0]
    assert filter_nones(body) == {
        "embeds": [
            {
                "color": 0x5C64F4,
                "title": "**Page 1!**",
                "url": "https://example.com/page/1",
                "description": "New Test Webcomic!",
            },
        ],
        "content": "<@&1>",
    }


def test_good_url_scheme(comic: Comic) -> None:
    """`http://` and `https://` url schemes are left unchanged."""
    entry1: Entry = {"link": "http://example.com/page/1", "title": "Page 1!"}
    entry2: Entry = {"link": "https://example.com/page/1", "title": "Page 1!"}
    body = _make_messages(comic, [entry1, entry2])[0]
    assert filter_nones(body) == {
        "embeds": [
            {
                "color": 0x5C64F4,
                "title": "**Page 1!**",
                "url": "http://example.com/page/1",
                "description": "New Test Webcomic!",
            },
            {
                "color": 0x5C64F4,
                "title": "**Page 1!**",
                "url": "https://example.com/page/1",
                "description": "New Test Webcomic!",
            },
        ],
        "content": "<@&1>",
    }


def test_no_title(comic: Comic) -> None:
    """When the RSS feed entry has no <title>, the name of the comic is used.

    Regression test for
    [0249766](https://github.com/mymoomin/RSStoWebhook/commit/0249766c715879891e3d21bb61bc537839020f5b),
    where a missing entry title caused the embed to not have a title.
    """
    entry: Entry = {"link": "hps://example.com/page/1"}
    body = _make_messages(comic, [entry])[0]
    assert filter_nones(body) == {
        "embeds": [
            {
                "color": 0x5C64F4,
                "title": "**Test Webcomic**",
                "url": "https://example.com/page/1",
                "description": "New Test Webcomic!",
            },
        ],
        "content": "<@&1>",
    }


def test_splits_big_updates(comic: Comic) -> None:
    num_entries = 32
    max_embeds_per_message = 10
    entries: list[Entry] = [
        {"link": f"hps://example.com/page/{i}"} for i in range(num_entries)
    ]
    messages = _make_messages(comic, entries)
    embeds_by_message = [message["embeds"] for message in messages]
    all_embeds = [embed for embeds in embeds_by_message for embed in embeds]

    assert len(messages) == math.ceil(num_entries / max_embeds_per_message)
    assert all(len(embeds) <= max_embeds_per_message for embeds in embeds_by_message)
    if len(embeds_by_message) > 1:
        assert all(
            len(embeds) == max_embeds_per_message for embeds in embeds_by_message[:-1]
        )
    assert len(all_embeds) == num_entries
