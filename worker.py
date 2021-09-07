import asyncio
import os
import sys
from datetime import datetime
from time import sleep

import aiohttp
import feedparser
import mmh3
import requests
from dotenv import load_dotenv
from feedparser.util import FeedParserDict
from pymongo import MongoClient
from pymongo.collection import Collection

from db_types import Comic, Entry


def get_new_entries(comic: Comic, feed: FeedParserDict, hash: int) -> list[Entry]:
    if comic["hash"] == hash:
        print("no changes")
        return ([], True)
    last_entries = comic["last_entries"]
    i = 0
    num_entries = len(feed["entries"])
    while i < 20 and i < num_entries:
        if feed["entries"][i]["link"] in last_entries:
            print(f"{i} new entries")
            return (list(reversed(feed["entries"][:i])), True)
        i += 1
    else:
        return (list(reversed(feed["entries"][:5])), False)


def make_body(comic: Comic, entry: Entry) -> dict:
    return {
        "username": comic["author"]["name"],
        "avatar_url": comic["author"]["url"],
        "content": f"<@&{comic['role_id']}>",
        "embeds": [
            {
                "color": comic["color"],
                "title": f"**{entry.get('title', comic['name'])}**",
                "url": entry["link"],
                "description": f"New {comic['name']}!",
            },
        ],
    }


async def get_feed(
    session: aiohttp.ClientSession, comic: Comic, hash_seed: int, **kwargs
) -> FeedParserDict:
    url = comic["url"]
    print(f"Requesting {url}")
    try:
        resp = await session.request("GET", url=url, **kwargs)
        data = await resp.text()
        print(f"Received data for {comic['name']}")
        feed = feedparser.parse(data)
        hash = mmh3.hash_bytes(data, hash_seed)
        print("Parsed feed")
        return (feed, hash)
    except Exception as e:
        print(f"Problem connecting to {comic['name']}")
        return (e, None)


async def get_feeds(
    comic_list: list[Comic], hash_seed: int, **kwargs
) -> list[FeedParserDict]:
    async with aiohttp.ClientSession() as session:
        tasks = [get_feed(session, comic, hash_seed, **kwargs) for comic in comic_list]
        feeds = await asyncio.gather(*tasks, return_exceptions=False)
        return feeds


def main(comics: Collection, hash_seed: int, webhook_url: str):
    start = datetime.now()
    comic_list: list[Comic] = list(comics.find())
    feeds_and_hashes = asyncio.get_event_loop().run_until_complete(
        get_feeds(comic_list, hash_seed, timeout=timeout)
    )
    print("done")
    comics_feeds_and_hashes = zip(comic_list, *zip(*feeds_and_hashes))

    counter = 1
    for comic, feed, hash in comics_feeds_and_hashes:
        print(f"Checking {comic['name']}")
        if isinstance(feed, Exception):
            print(f"{type(feed).__name__}: {str(feed)}")
        else:
            entries, found = get_new_entries(comic, feed, hash)
            if not found:
                print(
                    f"Couldn't find last entry for {comic['name']}, defaulting to most"
                    " recent entry"
                )
            for entry in entries:
                sleep(0.4) if counter != 0 else sleep(50)
                body = make_body(comic, entry)
                r = requests.post(webhook_url, None, body)
                print(f"{body['embeds'][0]['title']}: {r.status_code}: {r.reason}")
                h = r.headers
                print(
                    f"{h['x-ratelimit-remaining']} of {h['x-ratelimit-limit']} requests"
                    f" left in the next {h['x-ratelimit-reset-after']} seconds"
                )
                if r.status_code == 429:
                    print(r.json())
                    raise Exception("Ratelimit reached")
                counter = (counter + 1) % 30

            comics.update_one(
                {"name": comic["name"]},
                {
                    "$set": {"hash": hash},
                    "$push": {
                        "last_entries": {
                            "$each": [entry["link"] for entry in entries],
                            "$slice": -10,
                        }
                    },
                },
            )

    time_taken = (datetime.now() - start).seconds
    print(
        f"All feeds checked in {time_taken//60} minutes and {time_taken % 60} seconds"
    )


if __name__ == "__main__":
    load_dotenv()
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
    HASH_SEED = int(os.environ.get("HASH_SEED"), 16)
    MONGODB_URI = os.environ.get("MONGODB_URI")
    comics = MongoClient(MONGODB_URI)["discord_rss"]["comics"]

    timeout = aiohttp.ClientTimeout(sock_connect=5, sock_read=10)
    main(comics=comics, hash_seed=HASH_SEED, webhook_url=WEBHOOK_URL)
