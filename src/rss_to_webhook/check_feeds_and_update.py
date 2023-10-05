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
import os
import sys
import time
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp
import feedparser
import mmh3
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from requests import Response

from rss_to_webhook.constants import (
    DEFAULT_AIOHTTP_TIMEOUT,
    DEFAULT_GET_HEADERS,
    MAX_CACHED_ENTRIES,
)

if TYPE_CHECKING:  # pragma no cover
    from collections.abc import Iterable

    from feedparser.util import Entry
    from pymongo.collection import Collection

    from rss_to_webhook.db_types import CachingInfo, Comic, EntrySubset
    from rss_to_webhook.discord_types import Extras, Message


def main(
    comics: Collection[Comic],
    hash_seed: int,
    webhook_url: str,
    thread_webhook_url: str,
    timeout: aiohttp.ClientTimeout = DEFAULT_AIOHTTP_TIMEOUT,
) -> None:
    start = time.time()
    comic_list: list[Comic] = list(comics.find().sort("title"))
    comics_entries_headers = asyncio.get_event_loop().run_until_complete(
        get_changed_feeds(comic_list, hash_seed, comics, timeout=timeout)
    )

    rate_limiter = RateLimiter()

    for comic, entries, headers in comics_entries_headers:
        if entries:
            body = make_body(comic, entries)
            print(body)
            response = requests.post(
                f"{webhook_url}?wait=true", json=body, timeout=10, stream=True
            )
            print(
                f"{comic['title']}, {body['embeds'][0]['title']},"
                f" {body['embeds'][0]['url']}: {response.status_code}:"
                f" {response.reason}"
            )
            rate_limiter.limit_rate(webhook_url, response)
            if thread_id := comic.get("thread_id"):
                del body["content"]
                response = requests.post(
                    f"{thread_webhook_url}?wait=true&thread_id={thread_id}",
                    json=body,
                    timeout=10,
                )
                rate_limiter.limit_rate(thread_webhook_url, response)
        update(comics, comic, entries, headers)

    time_taken = time.time() - start
    print(
        f"Regular checks done in {int(time_taken) // 60} minutes and"
        f" {time_taken % 60:.2g} seconds"
    )


async def get_changed_feeds(
    comic_list: list[Comic],
    hash_seed: int,
    comics: Collection[Comic],
    **kwargs: Any,  # noqa: ANN401, RUF100
) -> Iterable[tuple[Comic, list[Entry], CachingInfo]]:
    async with aiohttp.ClientSession() as session:
        tasks = [
            get_feed_changes(session, comic, hash_seed, comics, **kwargs)
            for comic in comic_list
        ]
        feeds = await asyncio.gather(*tasks, return_exceptions=False)
        print("All feeds checked")
        return filter(None, feeds)


async def get_feed_changes(
    session: aiohttp.ClientSession,
    comic: Comic,
    hash_seed: int,
    comics: Collection[Comic],
    **kwargs: Any,  # noqa: ANN401, RUF100
) -> tuple[Comic, list[Entry], CachingInfo] | None:
    url = comic["url"]
    caching_headers = get_headers(comic)
    print(
        f"{comic['title']}: Requesting"
        f" {url}{f' with {caching_headers}' if caching_headers else ''}"
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
        new_entries = get_new_entries(comic["last_entries"], feed["entries"])
        print(f"{comic['title']}: {len(new_entries)} new entries")
        return (comic, new_entries, caching_info)
    except Exception as e:
        print(f"{comic['title']}: Problem connecting. {type(e).__name__}: {e} ")
        comics.update_one({"_id": comic["_id"]}, {"$inc": {"error_count": 1}})
        return None


def get_headers(comic: Comic) -> dict[str, str]:
    caching_headers: dict[str, str] = {}
    if "etag" in comic:
        caching_headers["If-None-Match"] = comic["etag"]
    if "last_modified" in comic:
        caching_headers["If-Modified-Since"] = comic["last_modified"]
    return caching_headers


def get_new_entries(
    last_entries: list[EntrySubset], current_entries: list[Entry]
) -> list[Entry]:
    last_urls = {entry["link"] for entry in last_entries}
    last_paths = {
        urlsplit(url).path.rstrip("/") + "?" + urlsplit(url).query for url in last_urls
    }
    last_pubdates = {
        entry["published"]  # pyright: ignore [reportTypedDictNotRequiredAccess]
        for entry in last_entries
        if entry.get("published") is not None  # We check that "publish" is a key here
    }
    last_ids = {entry.get("id") for entry in last_entries}
    new_entries: list[Entry] = []
    capped_entries = list(reversed(current_entries[:100]))
    max_entries = len(capped_entries)
    for entry in capped_entries:
        # The logic for this is that if an entry has a pubdate, use that for
        # comparison, if not use id, if not use link
        match entry:
            case {"published": date}:
                if date not in last_pubdates:
                    print("new date", date)
                    new_entries.append(entry)
            case {"id": id}:
                if id not in last_ids:
                    print("new id", id)
                    new_entries.append(entry)
            case {"link": link}:
                if (
                    urlsplit(link).path.rstrip("/") + "?" + urlsplit(link).query
                ) not in last_paths:
                    print("new link")
                    new_entries.append(entry)
            case _:
                print(f"malformed entry: {entry}")
    if len(new_entries) == max_entries:
        print("No last entry. Returning up to 100 most recent entries")
    else:
        print("Found last entry")
    return new_entries


def make_body(comic: Comic, entries: list[Entry]) -> Message:
    extras: Extras = {
        "username": comic.get("username"),
        "avatar_url": comic.get("avatar_url"),
    }
    if role_id := comic.get("role_id"):
        extras["content"] = f"<@&{role_id}>"
    embeds = []
    for entry in entries:
        if urlsplit(link := entry["link"]).scheme not in ["http", "https"]:
            print(f"{comic['title']}: bad url {entry['link']}")
            parts = urlsplit(link)
            link = urlunsplit(parts._replace(scheme="https"))
        embeds.append(
            {
                "color": comic.get("color", 0x5C64F4),
                "title": f"**{entry.get('title', comic['title'])}**",
                "url": link,
                "description": f"New {comic['title']}!",
            }
        )
    return {"embeds": embeds} | extras  # type: ignore[return-value]
    # mypy can't understand this assignment, but it is valid


class RateLimiter:
    """Limit rates to match Discord's API.

    This class stores the information necesary to obey Discord's hidden
    30 message/minute rate-limit on posts to webhooks in a channel, which
    is documented in [this tweet](https://twitter.com/lolpython/status/967621046277820416).

    Attributes:
        counter: Number of posts made in the current rate-limiting window.
        window_start: Timestamp of the start of the current window
        window_length: Length of the window, sourced from the tweet
        fuzz_factor: Additional safety margin.
            I know this margin is safe because I've tested it by posting 500
            messages to one webhook at this rate multiple times.
        fuzzed_window: The window plus the safety factor
        max_in_window: Maximum number of posts that can be made in each window.
            Sourced from the tweet again.
    """

    window_length: int = 60
    fuzz_factor: int = 1
    fuzzed_window: int = window_length + fuzz_factor
    max_in_window: int = 30
    buckets: dict[str, tuple[int, float]]

    def __init__(self) -> None:
        """Sets up rate-limiting buckets."""
        self.buckets = {}

    def limit_rate(self, bucket: str, response: Response) -> None:
        """Limits the rate on webhook posts per-webhook.

        This method will both respect explicit "X-RateLimit" headers in the
        response, and Discord's hidden rate limits.
        """
        if bucket not in self.buckets:
            self.buckets[bucket] = (1, time.time())
        counter, window_start = self.buckets[bucket]
        if counter == 0:
            window_time = time.time() - window_start
            print(f"Sleeping {self.fuzzed_window - window_time:.3} seconds")
            time.sleep(self.fuzzed_window - window_time)
            window_start = time.time()
        headers = response.headers
        remaining = headers.get("x-ratelimit-remaining")
        reset_after = headers.get("x-ratelimit-reset-after")
        print(
            f"{remaining} of"
            f" {headers.get('x-ratelimit-limit')} requests left in the next"
            f" {reset_after} seconds"
        )
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:  # 429
            print(response.json())
            response.raise_for_status()
        if remaining == "0" and reset_after is not None:
            print(f"Exhausted rate limit bucket. Retrying in {reset_after}")
            time.sleep(float(reset_after))
        counter = (counter + 1) % self.max_in_window
        self.buckets[bucket] = (counter, window_start)


def update(
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
    valid_keys = frozenset({"link", "id", "title", "published"})
    return [
        {key: value for key, value in entry.items() if key in valid_keys}  # type: ignore [misc]
        for entry in entries
    ]


def daily_checks(comics: Collection[Comic], webhook_url: str) -> None:
    start = time.time()
    comic_list: list[Comic] = list(comics.find({"dailies": {"$ne": []}}).sort("title"))

    rate_limiter = RateLimiter()
    for comic in comic_list:
        print(f"{comic['title']} daily: Posting")
        body = make_body(comic, comic["dailies"])  # type: ignore [arg-type]
        # The type is fine because `entries`` is only read, so it's
        # covariant, and so list[EntrySubset] is a subtype of list[Entry]
        response = requests.post(f"{webhook_url}?wait=true", json=body, timeout=10)
        rate_limiter.limit_rate(webhook_url, response)
        updates = len(comic["dailies"])
        word = "entry" if updates == 1 else "entries"
        print(f"{comic['title']} daily: Posted {len(comic['dailies'])} new {word}")
        comics.update_one({"_id": comic["_id"]}, {"$set": {"dailies": []}})

    time_taken = time.time() - start
    print(
        f"Daily checks done in {int(time_taken) // 60} minutes and"
        f" {time_taken % 60:.2g} seconds"
    )


if __name__ == "__main__":  # pragma no cover
    load_dotenv()
    HASH_SEED = int(os.environ["HASH_SEED"], 16)
    MONGODB_URI = os.environ["MONGODB_URI"]
    client: MongoClient[Comic] = MongoClient(MONGODB_URI)
    opts = [opt for opt in sys.argv[1:] if opt.startswith("-")]
    args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    if "--daily" in opts:
        print("Running daily checks")
        WEBHOOK_URL = os.environ["DAILY_WEBHOOK_URL"]
        comics = client["test-database"]["comics"]
        daily_checks(comics, WEBHOOK_URL)
    else:
        if "--test" in opts:
            print("testing testing")
            WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
            THREAD_WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
            comics = client["test-database"]["test-comics"]
        else:
            print("Running regular checks")
            WEBHOOK_URL = os.environ["WEBHOOK_URL"]
            THREAD_WEBHOOK_URL = os.environ["SD_WEBHOOK_URL"]
            comics = client["test-database"]["comics"]
        main(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
