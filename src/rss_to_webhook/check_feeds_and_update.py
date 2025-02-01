"""Pulls comic info from a database, checks for new pages, and posts them to discord.

This is intended as a script rather than a library, so if anything needs to be
imported by non-test code, it should probably be pulled out into a different
file? I might change my mind on that later though.

There are essentially two pipelines. One runs through `main` and does the
regular checks, posting new updates to the server and also to any relevant
threads in the Sleepless Domain server, as well as storing every page it posts
so the `daily` check can post it later. The other runs though `daily` and just
posts every update that has been marked for it to post, then clears that list.
"""

from __future__ import annotations

import asyncio
import enum
import json
import os
import time
from dataclasses import astuple, dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp
import feedparser
import mmh3
import requests
import typer
from dotenv import load_dotenv
from pymongo import MongoClient
from requests import Response

from rss_to_webhook.constants import (
    DEFAULT_AIOHTTP_TIMEOUT,
    DEFAULT_COLOR,
    DEFAULT_GET_HEADERS,
    HASH_SEED,
    LOOKBACK_LIMIT,
    MAX_CACHED_ENTRIES,
)
from rss_to_webhook.utils import batched

if TYPE_CHECKING:  # pragma no cover
    from collections.abc import Sequence

    from feedparser.util import Entry
    from pymongo.collection import Collection

    from rss_to_webhook.db_types import CachingInfo, Comic, EntrySubset
    from rss_to_webhook.discord_types import Embed, Extras, Message


class CheckType(enum.StrEnum):
    """Types for `check_feeds_and_update`."""

    regular = "regular"
    daily = "daily"
    test = "test"


# We can't use the `Annotate[CheckType, typer.Argument()]` form here because we
# use `from future import __annotations__`, which delays annotation evaluation
# and so breaks meaningful `Annotate` types.
def main(
    check_type: CheckType = typer.Argument(
        CheckType.regular,
        help=(
            "Use `regular` for normal checks, `daily` for daily, and `test` to run"
            " in testing mode."
        ),
    ),
) -> None:
    """Checks feeds for updates and posts them to Discord."""
    print("Running checks")
    load_dotenv()
    mongodb_uri = os.environ["MONGODB_URI"]
    db_name = os.environ["DB_NAME"]
    client: MongoClient[Comic] = MongoClient(mongodb_uri)
    if check_type == CheckType.daily:
        print("Running daily checks")
        webhook_url = os.environ["DAILY_WEBHOOK_URL"]
        comics = client[db_name]["comics"]
        daily_checks(comics, webhook_url)
    else:
        if check_type == CheckType.test:
            print("testing testing")
            webhook_url = os.environ["TEST_WEBHOOK_URL"]
            thread_webhook_url = os.environ["TEST_WEBHOOK_URL"]
            comics = client[db_name]["test-comics"]
        else:
            print("Running regular checks")
            webhook_url = os.environ["WEBHOOK_URL"]
            thread_webhook_url = os.environ["SD_WEBHOOK_URL"]
            comics = client[db_name]["comics"]
        regular_checks(comics, HASH_SEED, webhook_url, thread_webhook_url)


def regular_checks(
    comics: Collection[Comic],
    hash_seed: int,
    webhook_url: str,
    thread_webhook_url: str,
    timeout: aiohttp.ClientTimeout = DEFAULT_AIOHTTP_TIMEOUT,
) -> None:
    """Checks for updates, posts them to Discord, then persists the new state.

    Collects comics from `comics`, posts the updates to `webhook_url` and, when
    the comic has a `thread_id`, to the relevant thread in the channel pointed
    to by `thread_webhook_url`. Once deployed this will the webcomic channel in
    the Sleepless Domain server, but for now it's a secret channel in the "RSS
    but it's Discord" server. The new updates and some caching information are
    then persisted back to the database.

    Args:
        comics: A MongoDB collection containing all of the comics we track.
        hash_seed: A seed to be used to hash an RSS feed's content with, so we
            can detect unchanged feeds quickly.
        webhook_url: The URL to post normal updates to.
        thread_webhook_url: The URL to post thread updates to.
        timeout: A timeout to be used for all get requests.
    """
    start = time.time()
    comic_list: list[Comic] = list(comics.find().sort("title"))
    comics_entries_headers = asyncio.get_event_loop().run_until_complete(
        _get_changed_feeds(comic_list, hash_seed, comics, timeout=timeout)
    )
    print(
        f"{len(comics_entries_headers)} changed comics and"
        f" {len([1 for _, entries, _ in comics_entries_headers if len(entries) > 0])}"
        " updated comics"
    )

    rate_limiter = RateLimiter()

    for comic, entries, headers in comics_entries_headers:
        if entries:
            messages = _make_messages(comic, entries)
            for message in messages:
                print(f"{comic['title']}: new update {json.dumps(message)}")
                response = rate_limiter.post(f"{webhook_url}?wait=true", message)
                print(
                    f"{comic['title']} new post:, {message['embeds'][0]['title']},"
                    f" {message['embeds'][0]['url']}: {response.status_code}:"
                    f" {response.reason}"
                )
                if thread_id := comic.get("thread_id"):
                    if message.get("content"):
                        del message["content"]
                    response = rate_limiter.post(
                        f"{thread_webhook_url}?wait=true&thread_id={thread_id}", message
                    )
        _update(comics, comic, entries, headers)

    time_taken = time.time() - start
    print(
        f"Regular checks done in {int(time_taken) // 60} minutes and"
        f" {time_taken % 60:.2g} seconds"
    )


async def _get_changed_feeds(
    comic_list: list[Comic],
    hash_seed: int,
    comics: Collection[Comic],
    **kwargs: Any,  # noqa: ANN401, RUF100
) -> list[tuple[Comic, list[Entry], CachingInfo]]:
    async with aiohttp.ClientSession() as session:
        tasks = [
            _get_feed_changes(session, comic, hash_seed, comics, **kwargs)
            for comic in comic_list
        ]
        feeds = await asyncio.gather(*tasks)
        print("All feeds checked")
        return list(filter(None, feeds))


async def _get_feed_changes(
    session: aiohttp.ClientSession,
    comic: Comic,
    hash_seed: int,
    comics: Collection[Comic],
    **kwargs: Any,  # noqa: ANN401, RUF100
) -> tuple[Comic, list[Entry], CachingInfo] | None:
    url = comic["feed_url"]
    caching_headers = _get_headers(comic)
    print(
        f"{comic['title']}: Requesting"
        f" {url}{f' with {json.dumps(caching_headers)}.' if caching_headers else ''}"
    )
    try:
        r = await session.request(
            "GET",
            url=url,
            ssl=False,
            headers=DEFAULT_GET_HEADERS | caching_headers,
            **kwargs,
        )
        print(f"{comic['title']}: Got response {r.status}: {r.reason}")

        if r.status == HTTPStatus.NOT_MODIFIED:
            print(f"{comic['title']}: Cached response. No changes")
            return None

        if r.status != HTTPStatus.OK:
            print(f"{comic['title']}: HTTP {r.status}: {r.reason}")
            r.raise_for_status()

        data = await r.text()
        print(f"{comic['title']}: Received data")
        feed_hash = mmh3.hash_bytes(data, hash_seed)
        if feed_hash == comic["feed_hash"]:
            print(f"{comic['title']}: Hash match. No changes")
            return None

        caching_info: CachingInfo = {"feed_hash": feed_hash}
        if "ETag" in r.headers:
            caching_info["etag"] = r.headers["ETag"]
            print(f"{comic['title']}: Got new etag")
        if "Last-Modified" in r.headers:
            caching_info["last_modified"] = r.headers["Last-Modified"]
            print(f"{comic['title']}: Got new last-modified")

        feed = feedparser.parse(data)
        print(f"{comic['title']}: Parsed feed")
        new_entries = _get_new_entries(comic["last_entries"], feed["entries"])
        print(f"{comic['title']}: {len(new_entries)} new entries")
        return (comic, new_entries, caching_info)
    except Exception as e:  # noqa: BLE001
        print(f"{comic['title']}: Problem connecting. {type(e).__name__}: {e} ")
        comics.update_one(
            {"_id": comic["_id"]},
            {
                "$inc": {"error_count": 1},
                "$push": {"errors": f"{type(e).__name__}: {e}"},
            },
        )
        return None


def _get_headers(comic: Comic) -> dict[str, str]:
    caching_headers: dict[str, str] = {}
    if "etag" in comic:
        caching_headers["If-None-Match"] = comic["etag"]
    if "last_modified" in comic:
        caching_headers["If-Modified-Since"] = comic["last_modified"]
    return caching_headers


def _get_new_entries(
    last_entries: Sequence[EntrySubset], current_entries: Sequence[Entry]
) -> list[Entry]:
    """Gets new entries from an RSS feed.

    RSS provides several means of distinguishing between two feed entries.
    The intended ones are the <id> and the <link>, with <id> taking precedence.
    The <id> is intended as a permanent reference to an entry, to protect against
    a site changing all of their URLs and appearing to have all new entries, which
    happens fairly often.

    However, RSS feeds often don't have <id>s, and when they do, they often change
    their <id>s when the <link>s change, going against the intent of the <id> and
    making it unreliable to use for identity.

    On the upside, almost every RSS feed has a <pubDate> on each entry, which it
    turns out can be used for identifying identical entries, and never changes
    format in any case other than one from several years ago. We use this as our
    highest-precedence identity check, giving a hierarchy of <pubDate>, <id>, <link>.

    This function does a loop over the last `LOOKBACK_LIMIT` entries in the RSS feed,
    checking if each has been seen before by looping over each of the last-seen
    entries and seeing if any match, using the highest-precedence key that exists.
    This is somehow pretty fast. Small n really does just mean you can do whatever.

    The `if _normalise(entry["link"]) in last_paths` check is a performance optimisation
    over the expected check, comparing against `_normalise(old_entry["link"])`. I think
    that this is faster because checking for set membership is fairly fast, but
    normalising the <link> is quite slow. It feels weird though, and if this ever
    becomes an issue I'll rework this for a faster approach.
    """
    new_entries: list[Entry] = []
    capped_entries = list(reversed(current_entries[:LOOKBACK_LIMIT]))
    max_entries = len(capped_entries)
    last_paths = {_normalise(entry["link"]) for entry in last_entries}
    last_pubdates = {entry.get("published") for entry in last_entries}
    last_ids = {entry.get("id") for entry in last_entries}

    for entry in capped_entries:
        for old_entry in last_entries:
            if "published" in entry and "published" in old_entry:
                if entry["published"] in last_pubdates:
                    break
                continue
            if "id" in entry and "id" in old_entry:
                if entry["id"] in last_ids:
                    break
                continue
            if "link" in entry:
                if _normalise(entry["link"]) in last_paths:
                    break
                continue
            # This can't be reached in normal execution, but real-world RSS feeds
            # are malformed sometimes, so this is a sanity check. In the future,
            # this should probably be logged with log level warning.
            print(f"entry missing link: {entry}")  # type: ignore [unreachable]
            break
        else:
            new_entries.append(entry)
    if len(new_entries) == max_entries:
        print(f"No last entry. Returning up to {LOOKBACK_LIMIT} most recent entries")
    else:
        print("Found last entry")
    return new_entries


def _normalise(url: str) -> str:
    return urlsplit(url).path.rstrip("/") + "?" + urlsplit(url).query


def _make_messages(comic: Comic, entries: Sequence[EntrySubset]) -> list[Message]:
    extras: Extras = {
        "username": comic.get("username"),
        "avatar_url": comic.get("avatar_url"),
    }
    embeds: list[Embed] = []
    for entry in entries:
        if not (link := entry.get("link")):
            print(f"{comic['title']}: missing link {link}")
            continue
        if urlsplit(link).scheme not in {"http", "https"}:
            print(f"{comic['title']}: bad url {link}")
            parts = urlsplit(link)
            link = urlunsplit(parts._replace(scheme="https"))
        embeds.append({
            "color": comic.get("color", DEFAULT_COLOR),
            "title": _process_title(entry.get("title", comic["title"])),
            "url": link,
            "description": f"New {comic['title']}!",
        })
    # No typechecker can understand this assignment, but it is valid
    messages: list[Message] = [
        {"embeds": list(embed_chunk)} | extras for embed_chunk in batched(embeds, 10)  # type: ignore[misc]
    ]
    messages[0]["content"] = f"<@&{comic['role_id']}>"
    return messages


def _process_title(title: str) -> str:
    cropped_title = title[:252]
    return f"**{cropped_title}**"


@dataclass(slots=True)
class RateLimitState:
    """Stores state for rate limiting.

    Attributes:
        delay: The number of seconds to sleep for.
        counter: How many requests have been made in the last rate-limiting window.
        window_start: When the last window started. `None` if the last window has ended.
    """

    delay: float
    counter: int
    window_start: float | None


class RateLimiter:
    """Limit rates to match Discord's API.

    This class stores the information necessary to obey Discord's hidden
    30 message/minute rate-limit on posts to webhooks in a channel, which
    is documented in [this tweet](https://twitter.com/lolpython/status/967621046277820416).

    Attributes:
        window_length: Length of the window, sourced from the tweet.
        fuzz_factor: Additional safety margin.
            I know this margin is safe because I've tested it by posting 500
            messages to one webhook at this rate multiple times.
        fuzzed_window: The window plus the safety factor.
        max_in_window: Maximum number of posts that can be made in each window.
            Sourced from the tweet again.
        buckets: State for each rate-limiting bucket, indexed by webhook URL.
    """

    window_length: int = 60
    fuzz_factor: int = 1
    fuzzed_window: int = window_length + fuzz_factor
    max_in_window: int = 30
    buckets: dict[str, RateLimitState]

    def __init__(self) -> None:
        """Sets up rate-limiting buckets by url."""
        self.buckets = {}

    def post(self, url: str, body: Message) -> Response:
        """Posts to a webhook while respecting rate limits.

        This method will both respect explicit "X-RateLimit" headers in the
        response, and Discord's hidden rate limits.
        """
        if url not in self.buckets:
            self.buckets[url] = RateLimitState(
                delay=0, counter=1, window_start=time.time()
            )
        rate_limit_state = self.buckets[url]
        delay, counter, window_start = astuple(rate_limit_state)
        if delay != 0:
            print(f"Sleeping {round(delay, 2)} seconds")
            time.sleep(delay)
            rate_limit_state.delay = 0
            if window_start is None:
                rate_limit_state.window_start = time.time()

        # Setting `stream=True` fixed a heisenbug that would sometimes cause
        # "connection closed" errors in tests. It might be unnecessary, but on
        # the other hand removing it might look fine for months until the error
        # pops up again, so I'm leaving it for now.
        response = requests.post(url, json=body, timeout=20, stream=True)
        headers = response.headers
        remaining = headers.get("x-ratelimit-remaining")
        reset_after = headers.get("x-ratelimit-reset-after")
        print(
            f"{remaining} of"
            f" {headers.get('x-ratelimit-limit')} requests left in the next"
            f" {reset_after} seconds"
        )
        if response.status_code >= 400:  # noqa: PLR2004 # In the HTTP error range
            print(
                f"Error posting: {response.status_code} {response.reason}:"
                f" {response.json()}"
            )
            response.raise_for_status()
        if remaining == "0" and reset_after is not None:
            print(f"Exhausted rate limit bucket. Retrying in {reset_after}")
            rate_limit_state.delay = float(reset_after)
        rate_limit_state.counter = (counter + 1) % self.max_in_window
        print(counter)
        if counter == 0:
            window_time = time.time() - window_start
            print(f"Made {self.max_in_window} posts in {round(window_time, 2)}")
            rate_limit_state.delay = self.fuzzed_window - window_time
            rate_limit_state.window_start = None

        return response


def _update(
    comics: Collection[Comic],
    comic: Comic,
    entries: list[Entry],
    caching_info: CachingInfo,
) -> None:
    entry_subsets = strip_extra_data(entries)
    comics.update_one(
        {"_id": comic["_id"]},
        {
            "$set": caching_info,
            "$push": {
                "last_entries": {
                    "$each": entry_subsets,
                    "$slice": -MAX_CACHED_ENTRIES,
                },
                "dailies": {"$each": entry_subsets},
            },
        },
    )
    updates = len(entries)
    word = "entry" if updates == 1 else "entries"
    print(
        f"{comic['title']}: Set {', '.join(caching_info.keys())} and posted"
        f" {updates} new {word}"
    )


def strip_extra_data(entries: list[Entry]) -> list[EntrySubset]:
    """Strip extras from RSS feed entries before pushing them to the database.

    An RSS feed entry can contain a lot of extra information we don't care
    about, like each entry's description or author. Here we strip that extra
    junk away, leaving only the values we want to persist to the database.

    Args:
        entries: A list of entries from an RSS feed.

    Returns:
        A list of entries stripped of unnecessary values.
    """
    valid_keys = frozenset({"link", "id", "title", "published"})
    return [
        {key: value for key, value in entry.items() if key in valid_keys}  # type: ignore [misc]
        for entry in entries
    ]


def daily_checks(comics: Collection[Comic], webhook_url: str) -> None:
    """Posts new comics to the daily webhook, once a day.

    This does the daily checks, which don't actually have to check any RSS feeds
    because that work has already been done by `main`. `daily` can just post the
    new entries that have been pushed to `comic["dailies"]` for each comic, and
    then reset each comic's `dailies` value back to an empty array.

    Args:
        comics: A MongoDB collection containing all of the comics we track.
        webhook_url: The URL to post daily updates to.
    """
    start = time.time()
    comic_list: list[Comic] = list(comics.find({"dailies": {"$ne": []}}).sort("title"))
    print(f"Daily: {len(comic_list)} updated comics")

    rate_limiter = RateLimiter()
    for comic in comic_list:
        print(f"Daily {comic['title']}: Posting")
        messages = _make_messages(comic, comic["dailies"])
        for message in messages:
            rate_limiter.post(f"{webhook_url}?wait=true", message)
        updates = len(comic["dailies"])
        word = "entry" if updates == 1 else "entries"
        print(f"Daily {comic['title']}: Posted {len(comic['dailies'])} new {word}")
        comics.update_one({"_id": comic["_id"]}, {"$set": {"dailies": []}})

    time_taken = time.time() - start
    print(
        f"Daily checks done in {int(time_taken) // 60} minutes and"
        f" {time_taken % 60:.2g} seconds"
    )


if __name__ == "__main__":  # pragma no cover
    typer.run(main)
