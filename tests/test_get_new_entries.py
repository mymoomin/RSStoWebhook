from __future__ import annotations

import time
from typing import TYPE_CHECKING

from rss_to_webhook import constants
from rss_to_webhook.check_feeds_and_update import _get_new_entries

if TYPE_CHECKING:
    from collections.abc import Sequence

    from feedparser.util import Entry

    from rss_to_webhook.db_types import EntrySubset


def test_no_changes() -> None:
    """When nothing has changed since the last check, nothing is returned.

    Partial regression test for [#1](https://github.com/mymoomin/RSStoWebhook/issues/1)
    """
    last_seen: Sequence[EntrySubset] = [{"link": "https://example.com/page/1"}]
    feed_entries: Sequence[Entry] = [{"link": "https://example.com/page/1"}]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_missing_entry() -> None:
    """When there is one entry and all entries are new, it is returned."""
    last_seen: Sequence[EntrySubset] = [{"link": "https://example.com/page/1"}]
    feed_entries: Sequence[Entry] = []
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_new_update() -> None:
    """When there is one new update, it is posted."""
    last_seen: Sequence[EntrySubset] = [{"link": "https://example.com/page/1"}]
    feed_entries: Sequence[Entry] = [
        {"link": "https://example.com/page/2"},
        {"link": "https://example.com/page/1"},
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == [{"link": "https://example.com/page/2"}]


def test_new_updates() -> None:
    """When there are two new updates, they are returned from oldest to newest.

    Regression test for [#2](https://github.com/mymoomin/RSStoWebhook/issues/2)
    """
    last_seen: Sequence[EntrySubset] = [{"link": "https://example.com/page/1"}]
    feed_entries: Sequence[Entry] = [
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
    last_seen: Sequence[EntrySubset] = [
        {"link": "https://example.com/page/1"},
        {"link": "https://example.com/page/2"},
    ]
    feed_entries: Sequence[Entry] = [
        {"link": "https://example.com/page/1"},
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_all_new_feed() -> None:
    """When the last-seen entry isn't in the feed, the newest entries are returned.

    Regression test for [#3](https://github.com/mymoomin/RSStoWebhook/issues/3)
    """
    last_seen: Sequence[EntrySubset] = [{"link": "https://example.com/page/11"}]
    feed_entries: Sequence[Entry] = [
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
    all_entries: Sequence[Entry] = [
        {"link": f"https://example.com/page/{i}"} for i in range(1, 101)
    ]
    last_seen: Sequence[EntrySubset] = [{"link": "https://example.com/page/1"}]
    feed_entries: Sequence[Entry] = list(reversed(all_entries))
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == all_entries[1:]


def test_minor_url_change() -> None:
    """When a URL changes in a minor way, it is treated as the same URL.

    Regression test for [d2e8203](https://github.com/mymoomin/RSStoWebhook/commit/d2e82035639559aa25ec4ccfb79e8bf551e0d5d2).
    """
    last_seen: Sequence[EntrySubset] = [{"link": "http://example.com/page/1"}]
    feed_entries: Sequence[Entry] = [
        {"link": "http://example.com/page/1"},  # Same
        {"link": "https://example.com/page/1"},  # New scheme
        {"link": "http://example.com/page/1/"},  # Trailing slash
        {"link": "http://example.com/page/1?"},  # Trailing ?
        {"link": "http://example.com/page/1/?"},  # Both
        {"link": "http://exaple.com/page/1"},  # New netloc (might want this to fail)
        {"link": "https://exaple.com/page/1/?"},  # All changes
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_major_url_change() -> None:
    """When a URL changes to a close-but-different URL, it is seen as a different URL.

    Regression test for [e22f170](https://github.com/mymoomin/RSStoWebhook/commit/e22f17071a57331d26e5b62ea7e5a3f1949660a9).
    """
    last_seen: Sequence[EntrySubset] = [{"link": "https://example.com/page/1?v=1"}]
    feed_entries: Sequence[Entry] = [
        {"link": "https://example.com/page/1?v=2"},  # Change in query parameter
        {"link": "https://example.com/page/1"},  # Removal of query parameter
        {"link": "https://example.com/pge/1?v=1"},  # Small change in path
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == [
        {"link": "https://example.com/pge/1?v=1"},
        {"link": "https://example.com/page/1"},
        {"link": "https://example.com/page/1?v=2"},
    ]


def test_new_by_id() -> None:
    """When an entry differs only by id, it is still detected as new.

    This allows us to track comics like [Freefall](https://crosstimecafe.com/Webcomics/Feeds/Freefall.xml),
    where every entry has the same <link>.
    """
    last_seen: Sequence[EntrySubset] = [
        {"id": "page1", "link": "https://example.com/default"}
    ]
    feed_entries: Sequence[Entry] = [
        {"id": "page2", "link": "https://example.com/default"},
        {"id": "page1", "link": "https://example.com/default"},
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == [{"id": "page2", "link": "https://example.com/default"}]


def test_same_by_id() -> None:
    """When two entries have the same ID, they are treated as one entry.

    This means that if the <link>s in an RSS feed are all changed but the IDS
    aren't, then the script can avoid posting the whole RSS feed again.
    """
    last_seen: Sequence[EntrySubset] = [
        {"id": "page1", "link": "https://example.com/page/1"}
    ]
    feed_entries: Sequence[Entry] = [
        {"id": "page1", "link": "https://example.com/page/1?tracking=true"},
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_new_by_date() -> None:
    """When an entry differs only by pubdate, it is still detected as new.

    I'm not 100% sure this is desired behaviour. If a change breaks this test, it
    might be best to just remove the test.
    """
    last_seen: Sequence[EntrySubset] = [
        {
            "published": "Wed, 04 Oct 2023 01:40:51 -0400",
            "id": "https://example.com/page/1",
            "link": "https://example.com/page/1",
        }
    ]
    feed_entries: Sequence[Entry] = [
        {
            "published": "Thu, 05 Oct 2023 01:40:51 -0400",
            "id": "https://example.com/page/1",
            "link": "https://example.com/page/1",
        }
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == [
        {
            "published": "Thu, 05 Oct 2023 01:40:51 -0400",
            "id": "https://example.com/page/1",
            "link": "https://example.com/page/1",
        }
    ]


def test_same_by_date() -> None:
    """When two entries have the same pubdate, they are treated as the same entry.

    This allows us to handle cases where all a feed's URLs and IDs change to URLs that
    are the same but potentially different, but the dates are unchanged.
    """
    last_seen: Sequence[EntrySubset] = [
        {
            "published": "Wed, 04 Oct 2023 01:40:51 -0400",
            "id": "https://example.com/page/1",
            "link": "https://example.com/page/1",
        }
    ]
    feed_entries: Sequence[Entry] = [
        {
            "published": "Wed, 04 Oct 2023 01:40:51 -0400",
            "id": "https://example.com?page=1",
            "link": "https://example.com?page=1",
        },
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == []


def test_suddenly_date_and_id() -> None:
    """When a pubdate is added to an entry, it is still treated as the same entry.

    When an RSS feed adds pubdates or IDs, it tends to add them to all entries
    at once, including old entries. We want to make sure we don't repost the
    ones we've already seen. We do, however, want to return any new entries.
    """
    last_seen: Sequence[EntrySubset] = [{"link": "https://example.com/page/1"}]
    feed_entries: Sequence[Entry] = [
        {
            "published": "Thu, 05 Oct 2023 01:40:51 -0400",
            "id": "https://example.com/page/2",
            "link": "https://example.com/page/2",
        },
        {
            "published": "Wed, 04 Oct 2023 01:40:51 -0400",
            "id": "https://example.com/page/1",
            "link": "https://example.com/page/1",
        },
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == [
        {
            "published": "Thu, 05 Oct 2023 01:40:51 -0400",
            "id": "https://example.com/page/2",
            "link": "https://example.com/page/2",
        }
    ]


def test_skip_bad_entries() -> None:
    last_seen: Sequence[EntrySubset] = [{"link": "https://example.com/page/1"}]
    # This is an intentionally-wrong feed entry. It causes a type error here but
    # because we don't check that every feed pulled from the internet has a link
    # on all entries, this can still happen in the real world.
    feed_entries: Sequence[Entry] = [
        {"link": "https://example.com/page/2"},
        # the missing link
        {"title": "Hello!"},  # type: ignore [reportGeneralTypeIssues, typeddict-item]
        {"link": "https://example.com/page/1"},
    ]
    new_entries = _get_new_entries(last_seen, feed_entries)
    assert new_entries == [{"link": "https://example.com/page/2"}]


def test_new_entry_in_middle() -> None:
    """When a new entry appears in the middle of an RSS feed, it is still found.

    This allows us to check RSS feeds like The Property of Hate's or Freefall's, where
    new entries appear in the middle or at the end of the feed.
    """
    last_entries: Sequence[EntrySubset] = [
        {"link": "https://examples.com/track1/1"},
        {"link": "https://examples.com/track3/1"},
    ]
    feed_entries: Sequence[Entry] = [
        {"link": "https://examples.com/track3/1"},
        {"link": "https://examples.com/track2/1"},
        {"link": "https://examples.com/track1/1"},
    ]
    new_entries = _get_new_entries(last_entries, feed_entries)
    assert new_entries == [{"link": "https://examples.com/track2/1"}]


def test_performance() -> None:
    """The function takes a negligible amount of time (less than 0.01 seconds).

    According to [Usability Engineering](https://www.nngroup.com/articles/response-times-3-important-limits/),
    less than 0.1 seconds feels like instantaneous, so less than 0.01 seconds is
    essentially no time at all.

    Tests in multiple scenarios in the hopes that if slow cases exist this will
    hit at least one of them.
    """
    num_entries = constants.MAX_CACHED_ENTRIES
    negligible_time = 0.01  # Less than 0.1 seconds is perceived as instantaneous
    entries: Sequence[Entry] = [
        {
            "published": f"Thu, 05 Oct 2{i:0>3} 01:40:51 -0400",
            "id": f"https://examples.com/page/{i}",
            "link": f"https://examples.com/page/{i}",
        }
        for i in range(num_entries + 1)
    ]
    last_entries: Sequence[EntrySubset] = entries[:-1]

    feed_entries_all_values: Sequence[Entry] = entries[-100:]
    start_all_values = time.time()
    new_entries_all_values = _get_new_entries(last_entries, feed_entries_all_values)
    end_all_values = time.time()
    assert new_entries_all_values == [
        {
            "published": f"Thu, 05 Oct 2{num_entries:0>3} 01:40:51 -0400",
            "id": f"https://examples.com/page/{num_entries}",
            "link": f"https://examples.com/page/{num_entries}",
        }
    ]
    print(end_all_values - start_all_values)
    assert end_all_values - start_all_values < negligible_time

    feed_entries_just_link: Sequence[Entry] = [
        {"link": entry["link"]} for entry in feed_entries_all_values
    ]
    start_just_link = time.time()
    new_entries_just_link = _get_new_entries(last_entries, feed_entries_just_link)
    end_just_link = time.time()
    assert new_entries_just_link == [
        {"link": f"https://examples.com/page/{num_entries}"}
    ]
    assert end_just_link - start_just_link < negligible_time
