import pytest

from rss_to_webhook.db_types import Comic
from rss_to_webhook.worker import get_new_entries


@pytest.fixture()
def comic() -> Comic:
    return Comic(
        name="Test Webcomic",
        url="https://example.com/rss",
        hash=b"\xa9\x0c\x16\xe5\xe2\x8c6\xdd\x01}K\x85\x1fn\x8e\xd2",
        last_entries=["https://example.com/page/1"],
    )


@pytest.fixture()
def feed():
    return {
        "bozo": False,
        "encoding": "utf-8",
        "version": "rss20",
        "feed": {"title": "Test Webcomic"},
        "entries": [{"link": "https://example.com/page/1"}],
    }


def test_no_changes(comic, feed):
    """
    This is just the normal usage.

    Test asserts that `get_new_entries` functions when nothing has changed
    since the last check

    Partial regression test for [#1](https://github.com/mymoomin/RSStoWebhook/issues/1)
    """
    new_entries, found = get_new_entries(comic, feed, None)
    assert (new_entries, found) == ([], True)


def test_missing_entry(comic, feed):
    """
    Test asserts that `get_new_entries` functions when it can't find the last
    entry in the feed
    """
    feed["entries"] = []
    new_entries, found = get_new_entries(comic, feed, None)
    assert (new_entries, found) == ([], False)


def test_new_update(comic, feed):
    """
    Test asserts that when there is one new update, it is posted
    """
    feed["entries"] = [
        {"link": "https://example.com/page/2"},
        {"link": "https://example.com/page/1"},
    ]
    new_entries, found = get_new_entries(comic, feed, None)
    assert (new_entries, found) == ([{"link": "https://example.com/page/2"}], True)


def test_new_updates(comic, feed):
    """
    Test asserts that when there are many new updates, they are returned in the
    correct order (oldest to newest)

    Regression test for [#2](https://github.com/mymoomin/RSStoWebhook/issues/2)
    """
    feed["entries"] = [
        {"link": "https://example.com/page/3"},
        {"link": "https://example.com/page/2"},
        {"link": "https://example.com/page/1"},
    ]
    new_entries, found = get_new_entries(comic, feed, None)
    assert (new_entries, found) == (
        [
            {"link": "https://example.com/page/2"},
            {"link": "https://example.com/page/3"},
        ],
        True,
    )


def test_yanked_update(comic, feed):
    """
    Test asserts that when the most recent update is pulled but the one before
    has been seen already, nothing is done

    Partial regression test for [#1](https://github.com/mymoomin/RSStoWebhook/issues/1)
    """
    comic["last_entries"] = ["https://example.com/page/1", "https://example.com/page/2"]
    feed["entries"] = [
        {"link": "https://example.com/page/1"},
    ]
    new_entries, found = get_new_entries(comic, feed, None)
    assert (new_entries, found) == ([], True)


# GPT tests
@pytest.mark.parametrize(
    ("comic", "feed", "feed_hash", "expected_entries", "expected_found_last_entry"),
    [
        # Test case 1: No changes in the feed
        (
            {
                "name": "Comic1",
                "hash": b"hash1",
                "last_entries": ["https://example.com/entry1"],
            },
            {"entries": [{"link": "https://example.com/entry1"}]},
            b"hash1",
            [],
            True,
        ),
        # Test case 2: Some new entries in the feed
        (
            {
                "name": "Comic2",
                "hash": b"hash2",
                "last_entries": ["https://example.com/entry1"],
            },
            {
                "entries": [
                    {"link": "https://example.com/entry2"},
                    {"link": "https://example.com/entry1"},
                ]
            },
            b"not_hash2",
            [{"link": "https://example.com/entry2"}],
            True,
        ),
        # Test case 3: All entries are new in the feed
        (
            {
                "name": "Comic3",
                "hash": b"hash3",
                "last_entries": ["https://example.com/entry1"],
            },
            {
                "entries": [
                    {"link": "https://example.com/entry3"},
                    {"link": "https://example.com/entry2"},
                ]
            },
            b"not_hash3",
            [
                {"link": "https://example.com/entry2"},
                {"link": "https://example.com/entry3"},
            ],
            False,
        ),
        # Test case 4: No changes in the feed hash
        (
            {
                "name": "Comic4",
                "hash": b"hash4",
                "last_entries": ["https://example.com/entry1"],
            },
            {"entries": [{"link": "https://example.com/entry2"}]},
            b"hash4",
            [],
            True,
        ),
        # Test case 5: No entries in the feed
        (
            {
                "name": "Comic5",
                "hash": b"hash5",
                "last_entries": ["https://example.com/entry1"],
            },
            {"entries": []},
            b"not_hash5",
            [],
            False,
        ),
        # Test case 6: No entries in the feed, but hash has changed
        (
            {
                "name": "Comic6",
                "hash": b"hash6",
                "last_entries": ["https://example.com/entry1"],
            },
            {"entries": []},
            b"new_hash6",
            [],
            False,
        ),
    ],
)
def test_get_new_entries(
    comic, feed, feed_hash, expected_entries, expected_found_last_entry
):
    """
    These tests were generated by ChatGPT. I'm not sure how much value they add but I'm
    keeping them for now.

    Tests general usage
    """
    entries, found_last_entry = get_new_entries(comic, feed, feed_hash)
    assert entries == expected_entries
    assert found_last_entry == expected_found_last_entry
