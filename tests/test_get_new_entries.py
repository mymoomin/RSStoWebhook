from __future__ import annotations

from typing import TYPE_CHECKING

from rss_to_webhook.worker import get_new_entries

if TYPE_CHECKING:
    from feedparser.util import Entry


def test_no_changes() -> None:
    """
    This is just the normal usage.

    Test asserts that `get_new_entries` functions when nothing has changed
    since the last check

    Partial regression test for [#1](https://github.com/mymoomin/RSStoWebhook/issues/1)
    """
    last_seen = ["https://example.com/page/1"]
    feed_entries: list[Entry] = [{"link": "https://example.com/page/1"}]
    new_entries = get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_missing_entry() -> None:
    """
    Test asserts that `get_new_entries` functions when it can't find the last
    entry in the feed
    """
    last_seen = ["https://example.com/page/1"]
    feed_entries: list[Entry] = []
    new_entries = get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_new_update() -> None:
    """
    Test asserts that when there is one new update, it is posted
    """
    last_seen = ["https://example.com/page/1"]
    feed_entries: list[Entry] = [
        {"link": "https://example.com/page/2"},
        {"link": "https://example.com/page/1"},
    ]
    new_entries = get_new_entries(last_seen, feed_entries)
    assert new_entries == [{"link": "https://example.com/page/2"}]


def test_new_updates() -> None:
    """
    Test asserts that when there are two new updates, they are returned in the
    correct order (oldest to newest)

    Regression test for [#2](https://github.com/mymoomin/RSStoWebhook/issues/2)
    """
    last_seen = ["https://example.com/page/1"]
    feed_entries: list[Entry] = [
        {"link": "https://example.com/page/3"},
        {"link": "https://example.com/page/2"},
        {"link": "https://example.com/page/1"},
    ]
    new_entries = get_new_entries(last_seen, feed_entries)
    assert new_entries == [
        {"link": "https://example.com/page/2"},
        {"link": "https://example.com/page/3"},
    ]


def test_yanked_update() -> None:
    """
    Test asserts that when the most recent update is pulled but the one before
    has been seen already, nothing is done

    Partial regression test for [#1](https://github.com/mymoomin/RSStoWebhook/issues/1)
    """
    last_seen = ["https://example.com/page/1", "https://example.com/page/2"]
    feed_entries: list[Entry] = [
        {"link": "https://example.com/page/1"},
    ]
    new_entries = get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_all_new_feed() -> None:
    """
    Test asserts that when the last-seen entry isn't found in the feed, all
    entries are posted in order

    Regression test for [#3](https://github.com/mymoomin/RSStoWebhook/issues/3)
    """
    last_seen = ["https://example.com/page/11"]
    feed_entries: list[Entry] = [
        {"link": "https://example.com/page/2"},
        {"link": "https://example.com/page/1"},
    ]
    new_entries = get_new_entries(last_seen, feed_entries)
    assert new_entries == [
        {"link": "https://example.com/page/1"},
        {"link": "https://example.com/page/2"},
    ]


def test_many_updates_found() -> None:
    """
    Test asserts that when there are many new updates and the last-seen update
    is still in the feed, all the new updates are posted

    Partial regression test for [e33e902](https://github.com/mymoomin/RSStoWebhook/commit/e33e902cbf8d7a1ce4e5bb096386ca6e70469921)
    """
    all_entries: list[Entry] = [
        {"link": f"https://example.com/page/{i}"} for i in range(1, 101)
    ]
    last_seen = ["https://example.com/page/1"]
    feed_entries: list[Entry] = list(reversed(all_entries))
    new_entries = get_new_entries(last_seen, feed_entries)
    assert new_entries == all_entries[1:]


def test_many_updates_not_found() -> None:
    """
    Test asserts that when there are many new updates and the last-seen update
    is not in the feed, all the new updates are posted

    Partial regression test for [e33e902](https://github.com/mymoomin/RSStoWebhook/commit/e33e902cbf8d7a1ce4e5bb096386ca6e70469921)
    """
    all_entries: list[Entry] = [
        {"link": f"https://example.com/page/{i}"} for i in range(1, 101)
    ]
    last_seen = []
    feed_entries: list[Entry] = list(reversed(all_entries))
    new_entries = get_new_entries(last_seen, feed_entries)
    assert new_entries == all_entries


def test_minor_url_change() -> None:
    """
    Tests that when the URL for an entry changes in a semantically-equivalent
    way, it is recognised as the same URL

    Regression test for [d2e8203](https://github.com/mymoomin/RSStoWebhook/commit/d2e82035639559aa25ec4ccfb79e8bf551e0d5d2)
    """
    last_seen = ["https://example.com/page/1"]
    feed_entries: list[Entry] = [{"link": "http://example.com/page/1/"}]
    new_entries = get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_major_url_change() -> None:
    """
    Tests that when the URL for an entry changes in a semantically-inequivalent
    way, it is correctly not recognised as the same URL

    Regression test for [d2e8203](https://github.com/mymoomin/RSStoWebhook/commit/d2e82035639559aa25ec4ccfb79e8bf551e0d5d2)
    """
    last_seen = ["https://example.com/page/1?v=1"]
    feed_entries: list[Entry] = [{"link": "https://example.com/page/1?v=2"}]
    new_entries = get_new_entries(last_seen, feed_entries)
    assert new_entries == [{"link": "https://example.com/page/1?v=2"}]
