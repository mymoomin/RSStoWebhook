from __future__ import annotations

from typing import TYPE_CHECKING

from rss_to_webhook.check_feeds_and_update import _get_new_entries

if TYPE_CHECKING:
    from feedparser.util import Entry

    from rss_to_webhook.db_types import EntrySubset


def test_no_changes() -> None:
    """When nothing has changed since the last check, nothing is returned.

    Partial regression test for [#1](https://github.com/mymoomin/RSStoWebhook/issues/1)
    """
    last_seen: list[EntrySubset] = [{"link": "https://example.com/page/1"}]
    feed_entries: list[Entry] = [{"link": "https://example.com/page/1"}]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_missing_entry() -> None:
    """When there is one entry and all entries are new, it is returned."""
    last_seen: list[EntrySubset] = [{"link": "https://example.com/page/1"}]
    feed_entries: list[Entry] = []
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_new_update() -> None:
    """When there is one new update, it is posted."""
    last_seen: list[EntrySubset] = [{"link": "https://example.com/page/1"}]
    feed_entries: list[Entry] = [
        {"link": "https://example.com/page/2"},
        {"link": "https://example.com/page/1"},
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == [{"link": "https://example.com/page/2"}]


def test_new_updates() -> None:
    """When there are two new updates, they are returned from oldest to newest.

    Regression test for [#2](https://github.com/mymoomin/RSStoWebhook/issues/2)
    """
    last_seen: list[EntrySubset] = [{"link": "https://example.com/page/1"}]
    feed_entries: list[Entry] = [
        {"link": "https://example.com/page/3"},
        {"link": "https://example.com/page/2"},
        {"link": "https://example.com/page/1"},
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == [
        {"link": "https://example.com/page/2"},
        {"link": "https://example.com/page/3"},
    ]


def test_yanked_update() -> None:
    """`get_new_entries` can recognise older updates as having been seen before.

    Partial regression test for [#1](https://github.com/mymoomin/RSStoWebhook/issues/1)
    """
    last_seen: list[EntrySubset] = [
        {"link": "https://example.com/page/1"},
        {"link": "https://example.com/page/2"},
    ]
    feed_entries: list[Entry] = [
        {"link": "https://example.com/page/1"},
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_all_new_feed() -> None:
    """When the last-seen entry isn't in the feed, the newest entries are returned.

    Regression test for [#3](https://github.com/mymoomin/RSStoWebhook/issues/3)
    """
    last_seen: list[EntrySubset] = [{"link": "https://example.com/page/11"}]
    feed_entries: list[Entry] = [
        {"link": "https://example.com/page/2"},
        {"link": "https://example.com/page/1"},
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == [
        {"link": "https://example.com/page/1"},
        {"link": "https://example.com/page/2"},
    ]


def test_many_updates_found() -> None:
    """When there are many new updates, all the new updates are returned in order.

    Regression test for [e33e902](https://github.com/mymoomin/RSStoWebhook/commit/e33e902cbf8d7a1ce4e5bb096386ca6e70469921)
    """
    all_entries: list[Entry] = [
        {"link": f"https://example.com/page/{i}"} for i in range(1, 101)
    ]
    last_seen: list[EntrySubset] = [{"link": "https://example.com/page/1"}]
    feed_entries: list[Entry] = list(reversed(all_entries))
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == all_entries[1:]


def test_minor_url_change() -> None:
    """When a URL changes in a minor way, it is treated as the same URL.

    Regression test for [d2e8203](https://github.com/mymoomin/RSStoWebhook/commit/d2e82035639559aa25ec4ccfb79e8bf551e0d5d2).
    """
    last_seen: list[EntrySubset] = [{"link": "https://example.com/page/1"}]
    feed_entries: list[Entry] = [{"link": "http://example.com/page/1/?"}]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_major_url_change() -> None:
    """When a URL changes to a close-but-different URL, it is seen as a different URL.

    Regression test for [e22f170](https://github.com/mymoomin/RSStoWebhook/commit/e22f17071a57331d26e5b62ea7e5a3f1949660a9).
    """
    last_seen: list[EntrySubset] = [{"link": "https://example.com/page/1?v=1"}]
    feed_entries: list[Entry] = [{"link": "https://example.com/page/1?v=2"}]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == [{"link": "https://example.com/page/1?v=2"}]
