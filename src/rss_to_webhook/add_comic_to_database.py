import json
import os
from http import HTTPStatus
from pathlib import Path
from typing import NotRequired, TypedDict

import feedparser
import mmh3
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.results import UpdateResult
from requests.structures import CaseInsensitiveDict

from rss_to_webhook.check_feeds_and_update import strip_extra_data
from rss_to_webhook.constants import DEFAULT_GET_HEADERS
from rss_to_webhook.db_types import CachingInfo, Comic


class ComicData(TypedDict):
    title: str
    url: str
    role_id: int
    color: NotRequired[int]
    username: str
    avatar_url: str


def set_headers(
    comic: ComicData, headers: CaseInsensitiveDict[str], collection: Collection[Comic]
) -> None:
    new_headers = {}
    if "ETag" in headers:
        new_headers["etag"] = headers["ETag"]
        print(f"{comic['title']} has an ETag")
    if "Last-Modified" in headers:
        new_headers["last_modified"] = headers["Last-Modified"]
        print(f"{comic['title']} has a Last-Modified")
    if new_headers:
        collection.update_one({"title": comic["title"]}, {"$set": new_headers})
        print(f"Set caching headers for {comic['title']}")
    else:
        print(f"No headers for {comic['title']}")


def add_to_collection(
    comic: ComicData, collection: Collection[Comic], hash_seed: int
) -> UpdateResult:
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
    r = requests.get(comic["url"], headers=DEFAULT_GET_HEADERS, timeout=10)
    if r.status_code != HTTPStatus.OK:
        print(f"{comic['title']}, {comic['url']}:  HTTP {r.status_code}: {r.reason}")
        r.raise_for_status()
    feed_hash = mmh3.hash_bytes(r.text, hash_seed)
    feed = feedparser.parse(r.text)

    if not feed["entries"] or not feed["version"]:
        print(f"The rss feed for {comic['title']} is broken.")
        print(comic["url"])
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
                    "$slice": -400,
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
    comic_list: list[ComicData] = json.loads(
        Path("./scripts/new_comics.json").read_text()
    )
    for comic in comic_list:
        add_to_collection(comic, collection, HASH_SEED)
