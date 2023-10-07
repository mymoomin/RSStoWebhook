"""Adds comics to the database."""

import json
import os
from http import HTTPStatus
from pathlib import Path

import feedparser
import mmh3
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.results import UpdateResult
from requests.structures import CaseInsensitiveDict

from rss_to_webhook.check_feeds_and_update import strip_extra_data
from rss_to_webhook.constants import DEFAULT_GET_HEADERS, MAX_CACHED_ENTRIES
from rss_to_webhook.db_types import CachingInfo, Comic, DiscordComic


def set_headers(
    comic: Comic,
    headers: CaseInsensitiveDict[str],
    collection: Collection[Comic],
) -> None:
    """Sets the caching headers for a given comic."""
    new_headers = {}
    if "ETag" in headers:
        new_headers["etag"] = headers["ETag"]
        print(f"{comic['title']} has an ETag")
    if "Last-Modified" in headers:
        new_headers["last_modified"] = headers["Last-Modified"]
        print(f"{comic['title']} has a Last-Modified")
    if new_headers:
        collection.update_one({"_id": comic["_id"]}, {"$set": new_headers})
        print(f"Set caching headers for {comic['title']}")
    else:
        print(f"No headers for {comic['title']}")


def add_to_collection(
    comic: DiscordComic, collection: Collection[Comic], hash_seed: int
) -> UpdateResult:
    """Adds a comic to the given collection, setting RSS info as well."""
    result = collection.update_one(
        {"title": comic["title"]}, {"$set": comic}, upsert=True
    )
    if result.matched_count == 1:
        if result.modified_count == 0:
            print(f"Left {comic['title']} as-is")
            return result
        else:
            print(f"Updated {comic['title']}")
            return result
    assert (
        result.upserted_id
    ), "Comic neither updated not inserted. This shouldn't be able to happen. Aborting."
    print(f"Added {comic['title']}")

    print(f"Setting up RSS feed state for {comic['title']}")
    r = requests.get(comic["feed_url"], headers=DEFAULT_GET_HEADERS, timeout=10)
    if r.status_code != HTTPStatus.OK:
        print(
            f"{comic['title']}, {comic['feed_url']}:  HTTP {r.status_code}: {r.reason}"
        )
        r.raise_for_status()
    feed_hash = mmh3.hash_bytes(r.text, hash_seed)
    feed = feedparser.parse(r.text)

    if not feed["entries"] or not feed["version"]:
        print(f"The rss feed for {comic['title']} is broken.")
        print(comic["feed_url"])
        return result

    # Definitely a valid RSS feed now, so we can update the db

    caching_info: CachingInfo = {"feed_hash": feed_hash}
    if "ETag" in r.headers:
        caching_info["etag"] = r.headers["ETag"]
        print(f"{comic['title']}: Got new etag")
    if "Last-Modified" in r.headers:
        caching_info["last_modified"] = r.headers["Last-Modified"]
        print(f"{comic['title']}: Got new last-modified")

    last_entries = strip_extra_data(list(reversed(feed["entries"])))
    collection.update_one(
        {"title": comic["title"]},
        {
            "$push": {
                "last_entries": {
                    "$each": last_entries,
                    "$slice": -MAX_CACHED_ENTRIES,
                },
            },
            "$set": {"dailies": [], **caching_info},
        },
    )
    print(f"Set state for {comic['title']}")
    return result


if __name__ == "__main__":  # pragma: no cover
    load_dotenv()
    HASH_SEED = int(os.environ["HASH_SEED"], 16)
    MONGODB_URI = os.environ["MONGODB_URI"]
    client: MongoClient[Comic] = MongoClient(MONGODB_URI)
    collection = client["test-database"]["comics"]
    comic_list: list[DiscordComic] = json.loads(
        Path("./src/rss_to_webhook/scripts/new_comics.json").read_text()
    )
    for comic in comic_list:
        add_to_collection(comic, collection, HASH_SEED)
