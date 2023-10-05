from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from bson import ObjectId

from rss_to_webhook.check_feeds_and_update import _make_body
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
        url="https://example.com/rss",
        feed_hash=b"\xa9\x0c\x16\xe5\xe2\x8c6\xdd\x01}K\x85\x1fn\x8e\xd2",
        last_entries=[{"link": "https://example.com/page/0"}],
    )


def filter_nones(message: Message) -> Message:
    """Discord treats message values that are `None` as though they weren't in the
    dictionary at all, so `None` and missing are equivalent. Pytest doesn't.
    This normalises all `None` values to just be missing, to hide the difference.
    """
    return {key: value for key, value in message.items() if value is not None}  # type: ignore [reportGeneralTypeIssues, return-value]
    # This is correctly-typed because every key in `Message` is optional,
    # so removing keys doesn't change the type


def test_happy_path(comic: Comic) -> None:
    """Test asserts that `make_body` functions on the happy path.

    This is just the normal usage.
    """
    entry: Entry = {"link": "https://example.com/page/1", "title": "Page 1!"}
    body = _make_body(comic, [entry])
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
    """Test that `make_body` will correct bad url schemes.


    This is a regression test for
    [13a7171](https://github.com/mymoomin/RSStoWebhook/commit/13a7171be8f19164902a36e1f5abd587f852a303),
    where a bad url scheme caused the service to fail for multiple days.

    Test asserts that `make_body` will correct bad url schemes.
    """
    entry: Entry = {"link": "hps://example.com/page/1", "title": "Page 1!"}
    body = _make_body(comic, [entry])
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


def test_no_title(comic: Comic) -> None:
    """This is a regression test for
    [0249766](https://github.com/mymoomin/RSStoWebhook/commit/0249766c715879891e3d21bb61bc537839020f5b),
    where a missing entry title caused the embed to not have a title.

    Test asserts that even without a title the embed has a title.
    """
    entry: Entry = {"link": "hps://example.com/page/1"}
    body = _make_body(comic, [entry])
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


# GPT tests
@pytest.mark.parametrize(
    ("comic", "entry", "expected_output"),
    [
        # Test case 1: Minimal input
        (
            {
                "title": "Comic1",
                "url": "https://example.com/comic1",
                "username": "Author1",
                "avatar_url": "https://example.com/icon",
            },
            {
                "link": "https://example.com/entry1",
                "id": "1",
                "title": "Entry 1",
                "published": "2023-09-27",
            },
            {
                "embeds": [
                    {
                        "color": 0x5C64F4,
                        "title": "**Entry 1**",
                        "url": "https://example.com/entry1",
                        "description": "New Comic1!",
                    },
                ],
                "username": "Author1",
                "avatar_url": "https://example.com/icon",
            },
        ),
        # Test case 2: Test with role_id and thread_id
        (
            {
                "title": "Comic2",
                "url": "https://example.com/comic2",
                "role_id": 123,
                "username": "Author2",
                "avatar_url": "https://example.com/icon",
            },
            {
                "link": "https://example.com/entry2",
                "id": "2",
                "title": "Entry 2",
                "published": "2023-09-28",
            },
            {
                "embeds": [
                    {
                        "color": 0x5C64F4,
                        "title": "**Entry 2**",
                        "url": "https://example.com/entry2",
                        "description": "New Comic2!",
                    },
                ],
                "username": "Author2",
                "avatar_url": "https://example.com/icon",
                "content": "<@&123>",
            },
        ),
    ],
)
def test_gpt_make_body(comic: Comic, entry: Entry, expected_output: Message) -> None:
    """Tests general usage

    These tests were generated by ChatGPT. I'm not sure how much value they add but I'm
    keeping them for now.
    """
    result = _make_body(comic, [entry])
    assert filter_nones(result) == expected_output
