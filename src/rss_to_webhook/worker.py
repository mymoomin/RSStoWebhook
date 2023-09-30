from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlsplit, urlunsplit

import aiohttp
import feedparser
import mmh3
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

if TYPE_CHECKING:  # pragma no cover
    from collections.abc import Iterable

    from feedparser.util import Entry
    from pymongo.collection import Collection

    from rss_to_webhook.db_types import CachingInfo, Comic
    from rss_to_webhook.discord_types import Extras, Message


def get_new_entries(
    last_entries: list[str], current_entries: list[Entry]
) -> list[Entry]:
    last_paths = {
        urlsplit(url).path.rstrip("/") + "?" + urlsplit(url).query
        for url in last_entries
    }
    for i, entry in enumerate(current_entries):
        entry_parts = urlsplit(entry["link"])
        entry_path = entry_parts.path.rstrip("/") + "?" + entry_parts.query
        if entry_path in last_paths:
            print(f"{i} new entries")
            return list(reversed(current_entries[:i]))
    else:
        return list(reversed(current_entries[:100]))


def make_body(comic: Comic, entry: Entry) -> Message:
    extras: Extras = {}
    if author := comic.get("author"):
        extras["username"] = author["name"]
        extras["avatar_url"] = author["url"]
    if role_id := comic.get("role_id"):
        extras["content"] = f"<@&{role_id}>"
    if urlsplit(link := entry["link"]).scheme not in ["http", "https"]:
        parts = urlsplit(link)
        link = urlunsplit(parts._replace(scheme="https"))
    return {
        "embeds": [
            {
                "color": comic.get("color", 0x5C64F4),
                "title": f"**{entry.get('title', comic['name'])}**",
                "url": link,
                "description": f"New {comic['name']}!",
            },
        ],
    } | extras  # type: ignore[return-value]
    # mypy can't understand this assignment, but it is valid


def get_headers(comic: Comic) -> dict[str, str]:
    caching_headers = {}
    if "etag" in comic:
        caching_headers["If-None-Match"] = comic["etag"]
    if "last_modified" in comic:
        caching_headers["If-Modified-Since"] = comic["last_modified"]
    return caching_headers


async def get_feed(
    session: aiohttp.ClientSession,
    comic: Comic,
    hash_seed: int,
    comics: Collection[Comic],
    **kwargs: Any,  # noqa: ANN401, RUF100
) -> tuple[Comic, list[Entry], CachingInfo] | None:
    url = comic["url"]
    caching_headers = get_headers(comic)
    print(f"Requesting {url}")
    try:
        r = await session.request(
            "GET",
            url=url,
            ssl=False,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101"
                    " Firefox/96.0"
                ),
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
            | caching_headers,
            **kwargs,
        )
        data = await r.text()
        print(f"Received data for {comic['name']}")

        if r.status == HTTPStatus.NOT_MODIFIED:  # 304
            print("Cached response. No changes")
            return None

        if r.status != HTTPStatus.OK:  # 200
            print(f"HTTP {r.status}: {r.reason}")
            r.raise_for_status()

        feed = feedparser.parse(data)
        feed_hash = mmh3.hash_bytes(data, hash_seed)
        if feed_hash == comic["hash"]:
            print("no changes")
            return None

        caching_info: CachingInfo = {"hash": feed_hash}
        if "ETag" in r.headers:
            caching_info["etag"] = r.headers["ETag"]
        if "Last-Modified" in r.headers:
            caching_info["last_modified"] = r.headers["Last-Modified"]

        print("Parsed feed")
        new_entries = get_new_entries(comic["last_entries"], feed["entries"])
        return (comic, new_entries, caching_info)
    except Exception as e:
        print(f"Problem connecting to {comic['name']}. {type(e).__name__}: {e} ")
        comics.update_one({"_id": comic["_id"]}, {"$inc": {"error_count": 1}})
        return None


async def get_feeds(
    comic_list: list[Comic],
    hash_seed: int,
    comics: Collection[Comic],
    **kwargs: Any,  # noqa: ANN401, RUF100
) -> Iterable[tuple[Comic, list[Entry], CachingInfo]]:
    async with aiohttp.ClientSession() as session:
        tasks = [
            get_feed(session, comic, hash_seed, comics, **kwargs)
            for comic in comic_list
        ]
        feeds = await asyncio.gather(*tasks, return_exceptions=False)
        return filter(None, feeds)


@dataclass(slots=True)
class RateLimitState:
    counter: int
    chunk_start: float
    window_length: ClassVar[int] = 60
    fuzz_factor: ClassVar[int] = 1
    chunk_length: ClassVar[int] = window_length + fuzz_factor


def post(
    webhook_url: str, comic: Comic, entries: list[Entry], state: RateLimitState
) -> None:
    for entry in entries:
        if state.counter == 0:
            chunk_time = time.time() - state.chunk_start
            print(f"Sleeping {state.chunk_length - chunk_time:.3} seconds")
            time.sleep(state.chunk_length - chunk_time)
            state.chunk_start = time.time()
        body = make_body(comic, entry)
        if thread_id := comic.get("thread_id"):
            url = f"{webhook_url}?thread_id={thread_id}&wait=true"
        else:
            url = f"{webhook_url}?wait=true"
        r = requests.post(url, None, body, timeout=10)
        print(f"{body['embeds'][0]['url']}: {r.status_code}: {r.reason}")
        h = r.headers
        remaining = h.get("x-ratelimit-remaining")
        reset_after = h.get("x-ratelimit-reset-after")
        print(
            f"{remaining} of"
            f" {h.get('x-ratelimit-limit')} requests left in the next"
            f" {reset_after} seconds"
        )
        if r.status_code == HTTPStatus.TOO_MANY_REQUESTS:  # 429
            print(r.json())
            r.raise_for_status()
        if remaining == "0" and reset_after is not None:
            print(f"Exhausted rate limit bucket. Retrying in {reset_after}")
            time.sleep(float(reset_after))
        state.counter = (state.counter + 1) % 30


def update(
    comics: Collection[Comic],
    comic: Comic,
    entries: list[Entry],
    caching_info: CachingInfo,
) -> None:
    comics.update_one(
        {"_id": comic["_id"]},
        {
            "$set": caching_info,
            "$push": {
                "last_entries": {
                    "$each": [entry["link"] for entry in entries],
                    "$slice": -10,
                }
            },
        },
    )


def main(
    comics: Collection[Comic],
    hash_seed: int,
    webhook_url: str,
    timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
        sock_connect=15, sock_read=10
    ),
) -> None:
    start = time.time()
    comic_list: list[Comic] = list(comics.find())
    comics_entries_headers = asyncio.get_event_loop().run_until_complete(
        get_feeds(comic_list, hash_seed, comics, timeout=timeout)
    )
    print("done")

    ratelimit_state = RateLimitState(1, time.time())
    for comic, entries, headers in comics_entries_headers:
        post(webhook_url, comic, entries, ratelimit_state)
        update(comics, comic, entries, headers)

    time_taken = time.time() - start
    print(
        f"All feeds checked in {int(time_taken)//60} minutes and"
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
        comics = client["discord_rss"]["daily_comics"]
    elif "--test" in opts:
        print("testing testing")
        WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
        comics = client["discord_rss"]["test_comics"]
    else:
        WEBHOOK_URL = os.environ["WEBHOOK_URL"]
        comics = client["discord_rss"]["comics"]
    timeout = aiohttp.ClientTimeout(sock_connect=15, sock_read=10)
    main(
        comics=comics,
        hash_seed=HASH_SEED,
        webhook_url=WEBHOOK_URL,
    )

    WEBHOOK_URL = os.environ["SD_WEBHOOK_URL"]
    comics = client["discord_rss"]["server_comics"]
    main(comics=comics, hash_seed=HASH_SEED, webhook_url=WEBHOOK_URL)
