from __future__ import annotations

import asyncio
import os
import sys
import time
from time import sleep
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp
import feedparser
import mmh3
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

if TYPE_CHECKING:
    from feedparser.util import Entry, FeedParserDict
    from multidict import CIMultiDictProxy
    from pymongo.collection import Collection
    from src.rss_to_webhook.db_types import Comic, Extras


def get_new_entries(
    comic: Comic, feed: FeedParserDict, feed_hash: bytes | None
) -> tuple[list[Entry], bool]:
    if comic["hash"] == feed_hash:
        print("no changes")
        return ([], True)
    last_entries = comic["last_entries"]
    i = 0
    num_entries = len(feed.entries)
    last_paths = [
        urlsplit(url).path.rstrip("/") + "?" + urlsplit(url).query
        for url in last_entries
    ]
    while i < 100 and i < num_entries:
        entry_parts = urlsplit(feed.entries[i]["link"])
        entry_path = entry_parts.path.rstrip("/") + "?" + entry_parts.query
        if entry_path in last_paths:
            print(f"{i} new entries")
            return list(reversed(feed.entries[:i])), True
        i += 1
    else:
        return list(reversed(feed.entries[:30])), False


def make_body(comic: Comic, entry: Entry) -> dict:
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
    } | extras


def get_headers(comic: Comic) -> dict[str, str]:
    caching_headers = {}
    if "etag" in comic:
        caching_headers["If-None-Match"] = comic["etag"]
    if "last_modified" in comic:
        caching_headers["If-Modified-Since"] = comic["last_modified"]
    return caching_headers


def set_headers(
    comic: Comic, headers: CIMultiDictProxy[str], comics: Collection[Comic]
) -> None:
    new_headers = {}
    if "ETag" in headers:
        new_headers["etag"] = headers["ETag"]
    if "Last-Modified" in headers:
        new_headers["last_modified"] = headers["Last-Modified"]
    if new_headers:
        result = comics.update_one({"name": comic["name"]}, {"$set": new_headers})
        if result.modified_count != 0:
            print(f"Updated caching headers for {comic['name']}")


async def get_feed(
    session: aiohttp.ClientSession,
    comic: Comic,
    hash_seed: int,
    comics: Collection[Comic],
    **kwargs: Any,  # noqa: ANN401
) -> tuple[FeedParserDict | Exception | None, bytes | None]:
    url = comic["url"]
    caching_headers = get_headers(comic)
    print(f"Requesting {url}")
    try:
        resp = await session.request(
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
        data = await resp.text()
        print(f"Received data for {comic['name']}")
        if resp.status == 304:
            return None, None
        if resp.status != 200:
            print(f"HTTP {resp.status}: {resp.reason}")
            resp.raise_for_status()
        feed = feedparser.parse(data)
        feed_hash = mmh3.hash_bytes(data, hash_seed)
        set_headers(comic, resp.headers, comics)
        print("Parsed feed")
        return feed, feed_hash
    except Exception as e:
        print(f"Problem connecting to {comic['name']}")
        return e, None


async def get_feeds(
    comic_list: list[Comic],
    hash_seed: int,
    comics: Collection[Comic],
    **kwargs: Any,  # noqa: ANN401
) -> list[tuple[FeedParserDict | Exception | None, bytes | None]]:
    async with aiohttp.ClientSession() as session:
        tasks = [
            get_feed(session, comic, hash_seed, comics, **kwargs)
            for comic in comic_list
        ]
        feeds = await asyncio.gather(*tasks, return_exceptions=False)
        return feeds


def main(
    comics: Collection,
    hash_seed: int,
    webhook_url: str,
    timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(
        sock_connect=15, sock_read=10
    ),
) -> None:
    start = time.time()
    comic_list: list[Comic] = list(comics.find())
    feeds_and_hashes = asyncio.get_event_loop().run_until_complete(
        get_feeds(comic_list, hash_seed, comics, timeout=timeout)
    )
    print("done")
    comics_feeds_and_hashes: zip[
        tuple[Comic, FeedParserDict | Exception | None, bytes | None]
    ] = zip(
        comic_list, *zip(*feeds_and_hashes)
    )  # pyright: ignore [reportGeneralTypeIssues]
    # mypy understands this just fine, but Pyright has issues.

    counter = 1
    for comic, feed, feed_hash in comics_feeds_and_hashes:
        print(f"Checking {comic['name']}")
        if isinstance(feed, Exception):
            print(f"{type(feed).__name__}: {feed}")
        elif not feed:
            print("Cached response. No changes")
        else:
            entries, found = get_new_entries(comic, feed, feed_hash)
            if not found:
                print(
                    f"Couldn't find last entry for {comic['name']}, defaulting to"
                    " most recent entries"
                )
            for entry in entries:
                sleep(0.4) if counter != 0 else sleep(50)
                body = make_body(comic, entry)
                if thread_id := comic.get("thread_id"):
                    url = f"{webhook_url}?thread_id={thread_id}&wait=true"
                else:
                    url = f"{webhook_url}?wait=true"
                r = requests.post(url, None, body, timeout=10)
                print(f"{body['embeds'][0]['title']}: {r.status_code}: {r.reason}")
                h = r.headers
                print(
                    f"{h.get('x-ratelimit-remaining')} of"
                    f" {h.get('x-ratelimit-limit')} requests left in the next"
                    f" {h.get('x-ratelimit-reset-after')} seconds"
                )
                if r.status_code == 429:
                    print(r.json())
                    r.raise_for_status()
                counter = (counter + 1) % 30

            comics.update_one(
                {"name": comic["name"]},
                {
                    "$set": {"hash": feed_hash},
                    "$push": {
                        "last_entries": {
                            "$each": [entry["link"] for entry in entries],
                            "$slice": -10,
                        }
                    },
                },
            )

    time_taken = time.time() - start
    print(
        f"All feeds checked in {int(time_taken)//60} minutes and"
        f" {time_taken % 60:.2g} seconds"
    )


if __name__ == "__main__":
    load_dotenv()
    HASH_SEED = int(os.environ["HASH_SEED"], 16)
    MONGODB_URI = os.environ["MONGODB_URI"]
    opts = [opt for opt in sys.argv[1:] if opt.startswith("-")]
    args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    if "--daily" in opts:
        print("Running daily checks")
        WEBHOOK_URL = os.environ["DAILY_WEBHOOK_URL"]
        comics: Collection = MongoClient(MONGODB_URI)["discord_rss"]["daily_comics"]
    else:
        WEBHOOK_URL = os.environ["WEBHOOK_URL"]
        comics = MongoClient(MONGODB_URI)["discord_rss"]["comics"]
    timeout = aiohttp.ClientTimeout(sock_connect=15, sock_read=10)
    main(
        comics=comics,
        hash_seed=HASH_SEED,
        webhook_url=WEBHOOK_URL,
    )

    WEBHOOK_URL = os.environ["SD_WEBHOOK_URL"]
    comics = MongoClient(MONGODB_URI)["discord_rss"]["server_comics"]
    main(comics=comics, hash_seed=HASH_SEED, webhook_url=WEBHOOK_URL)
