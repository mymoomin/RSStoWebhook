"""Tools for modifying and querying the database."""

import json
import os
from pathlib import Path

import feedparser
import mmh3
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.results import InsertOneResult, UpdateResult

from rss_to_webhook.check_feeds_and_update import strip_extra_data
from rss_to_webhook.constants import DEFAULT_GET_HEADERS, HASH_SEED
from rss_to_webhook.db_types import CachingInfo, Comic, DiscordComic


def add_to_collection(
    comic_data: DiscordComic, collection: Collection[Comic], hash_seed: int
) -> UpdateResult | InsertOneResult:
    """Adds a comic to the given collection, setting RSS info as well."""
    result = collection.update_one({"title": comic_data["title"]}, {"$set": comic_data})
    if result.matched_count == 1:
        # The comic is already in the database
        if result.modified_count == 0:
            # and nothing has changed
            print(f"Left {comic_data['title']} as-is")
            return result
        else:
            # and we've just updated something about it
            print(f"Updated {comic_data['title']}")
            return result
    # The comic is not in the database
    print(f"Adding {comic_data['title']}")

    print(f"Setting up RSS feed state for {comic_data['title']}")
    r = requests.get(comic_data["feed_url"], headers=DEFAULT_GET_HEADERS, timeout=10)
    if r.status_code >= 400:  # noqa: PLR2004 Indicates an HTTP Error
        print(
            f"{comic_data['title']}, {comic_data['feed_url']}:  HTTP {r.status_code}:"
            f" {r.reason}"
        )
        r.raise_for_status()
        raise AssertionError("Unreachable")  # pragma: no cover
    feed_hash = mmh3.hash_bytes(r.text, hash_seed)
    feed = feedparser.parse(r.text)

    if not feed["entries"] or not feed["version"]:
        print(f"The rss feed for {comic_data['title']} is broken.")
        print(comic_data["feed_url"])
        return result

    # Definitely a valid RSS feed now, so we can update the db

    caching_info: CachingInfo = {"feed_hash": feed_hash}
    if "ETag" in r.headers:
        caching_info["etag"] = r.headers["ETag"]
        print(f"{comic_data['title']}: Got new etag")
    if "Last-Modified" in r.headers:
        caching_info["last_modified"] = r.headers["Last-Modified"]
        print(f"{comic_data['title']}: Got new last-modified")

    last_entries = strip_extra_data(list(reversed(feed["entries"])))
    new_comic = Comic(
        **comic_data, **caching_info, last_entries=last_entries, dailies=[]
    )  # type: ignore [reportGeneralTypeIssues, typeddict-item]
    insert_result = collection.insert_one(new_comic)
    print(f"Added {comic_data['title']}")
    return insert_result


if __name__ == "__main__":  # pragma: no cover
    load_dotenv()
    MONGODB_URI = os.environ["MONGODB_URI"]
    DB_NAME = os.environ["DB_NAME"]
    client: MongoClient[Comic] = MongoClient(MONGODB_URI)
    collection = client[DB_NAME]["comics"]
    comic_list: list[DiscordComic] = json.loads(
        Path("./src/rss_to_webhook/scripts/new_comics.json").read_text(encoding="utf-8")
    )
    for comic in comic_list:
        add_to_collection(comic, collection, HASH_SEED)
