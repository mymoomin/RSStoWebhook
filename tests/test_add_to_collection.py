from __future__ import annotations

import os
from typing import TYPE_CHECKING

import mmh3
import pytest
from bson import Int64, ObjectId
from dotenv import load_dotenv
from mongomock import Collection, MongoClient
from pymongo.results import UpdateResult
from requests import HTTPError
from responses import RequestsMock

from rss_to_webhook.constants import HASH_SEED
from rss_to_webhook.db_operations import add_to_collection

if TYPE_CHECKING:
    from collections.abc import Generator

    from rss_to_webhook.db_types import Comic, DiscordComic

load_dotenv(".env.example")
WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
THREAD_WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]


@pytest.fixture
def comic() -> DiscordComic:
    return {
        "title": "Sleepless Domain",
        "feed_url": "http://www.sleeplessdomain.com/comic/rss",
        "role_id": Int64("581531863127031868"),
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
    }


@pytest.fixture
def rss() -> Generator[RequestsMock, None, None]:
    with RequestsMock(assert_all_requests_are_fired=False) as responses:
        responses.get(
            "http://www.sleeplessdomain.com/comic/rss",
            status=200,
            body=example_feed,
        )
        yield responses


@pytest.fixture
def collection_with_sd() -> Collection[Comic]:
    client: MongoClient[Comic] = MongoClient()
    collection = client.db.collection
    comic: Comic = {
        "_id": ObjectId("111111111111111111111111"),
        "title": "Sleepless Domain",
        "feed_url": "http://www.sleeplessdomain.com/comic/rss",
        "role_id": Int64("581531863127031868"),
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
        "feed_hash": mmh3.hash_bytes(example_feed, HASH_SEED),
        "dailies": [],
        "last_entries": [
            {
                "title": "Sleepless Domain - Chapter 21 - Interstitial",
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-33",
                "published": "Mon, 11 Sep 2023 15:01:54 -0400",
                "id": "https://www.sleeplessdomain.com/comic/chapter-21-page-33",
            },
            {
                "title": "Sleepless Domain - Chapter 22 - Page 1",
                "link": "https://www.sleeplessdomain.com/comic/chapter-22-page-1",
                "published": "Tue, 19 Sep 2023 15:12:58 -0400",
                "id": "https://www.sleeplessdomain.com/comic/chapter-22-page-1",
            },
            {
                "title": "Sleepless Domain - Chapter 22 - Page 2",
                "link": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
                "published": "Tue, 26 Sep 2023 01:39:48 -0400",
                "id": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
            },
        ],
    }
    collection.insert_one(comic)
    return collection


@pytest.mark.usefixtures("rss")
def test_add_valid_comic() -> None:
    client: MongoClient[Comic] = MongoClient()
    collection = client.db.collection
    comic_data: DiscordComic = {
        "title": "Sleepless Domain",
        "feed_url": "http://www.sleeplessdomain.com/comic/rss",
        "role_id": 581531863127031868,
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
    }
    add_to_collection(comic_data, collection, HASH_SEED)
    comic = collection.find_one({"title": comic_data["title"]})
    assert comic
    assert "_id" in comic
    comic_less_id = dict(comic)
    del comic_less_id["_id"]
    assert comic_less_id == {
        "title": "Sleepless Domain",
        "feed_url": "http://www.sleeplessdomain.com/comic/rss",
        "role_id": Int64("581531863127031868"),
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
        "feed_hash": mmh3.hash_bytes(example_feed, HASH_SEED),
        "dailies": [],
        "last_entries": [
            {
                "title": "Sleepless Domain - Chapter 21 - Interstitial",
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-33",
                "published": "Mon, 11 Sep 2023 15:01:54 -0400",
                "id": "https://www.sleeplessdomain.com/comic/chapter-21-page-33",
            },
            {
                "title": "Sleepless Domain - Chapter 22 - Page 1",
                "link": "https://www.sleeplessdomain.com/comic/chapter-22-page-1",
                "published": "Tue, 19 Sep 2023 15:12:58 -0400",
                "id": "https://www.sleeplessdomain.com/comic/chapter-22-page-1",
            },
            {
                "title": "Sleepless Domain - Chapter 22 - Page 2",
                "link": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
                "published": "Tue, 26 Sep 2023 01:39:48 -0400",
                "id": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
            },
        ],
    }


def test_sets_caching_headers(rss: RequestsMock) -> None:
    client: MongoClient[Comic] = MongoClient()
    collection = client.db.collection
    comic_data: DiscordComic = {
        "title": "Sleepless Domain",
        "feed_url": "http://www.sleeplessdomain.com/comic/rss+caching",
        "role_id": 581531863127031868,
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
    }
    rss.get(
        "http://www.sleeplessdomain.com/comic/rss+caching",
        status=200,
        body=example_feed,
        headers={
            "ETag": '"f56-6062f676a7367-gzip"',
            "Last-Modified": "Wed, 27 Sep 2023 20:10:14 GMT",
        },
    )
    add_to_collection(comic_data, collection, HASH_SEED)
    comic = collection.find_one({"title": comic_data["title"]})
    assert comic
    assert "_id" in comic
    comic_less_id = dict(comic)
    del comic_less_id["_id"]
    assert comic_less_id == {
        "title": "Sleepless Domain",
        "feed_url": "http://www.sleeplessdomain.com/comic/rss+caching",
        "role_id": Int64("581531863127031868"),
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
        "feed_hash": mmh3.hash_bytes(example_feed, HASH_SEED),
        "etag": '"f56-6062f676a7367-gzip"',
        "last_modified": "Wed, 27 Sep 2023 20:10:14 GMT",
        "dailies": [],
        "last_entries": [
            {
                "title": "Sleepless Domain - Chapter 21 - Interstitial",
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-33",
                "published": "Mon, 11 Sep 2023 15:01:54 -0400",
                "id": "https://www.sleeplessdomain.com/comic/chapter-21-page-33",
            },
            {
                "title": "Sleepless Domain - Chapter 22 - Page 1",
                "link": "https://www.sleeplessdomain.com/comic/chapter-22-page-1",
                "published": "Tue, 19 Sep 2023 15:12:58 -0400",
                "id": "https://www.sleeplessdomain.com/comic/chapter-22-page-1",
            },
            {
                "title": "Sleepless Domain - Chapter 22 - Page 2",
                "link": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
                "published": "Tue, 26 Sep 2023 01:39:48 -0400",
                "id": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
            },
        ],
    }


def test_no_changes(collection_with_sd: Collection[Comic], rss: RequestsMock) -> None:
    """When a pre-existing comic is added, no changes are made."""
    comic_data: DiscordComic = {
        "title": "Sleepless Domain",
        "feed_url": "http://www.sleeplessdomain.com/comic/rss",
        "role_id": 581531863127031868,
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
    }
    update_result = add_to_collection(comic_data, collection_with_sd, HASH_SEED)
    assert isinstance(update_result, UpdateResult)
    assert update_result.matched_count == 1
    assert update_result.modified_count == 0
    assert len(rss.calls) == 0


def test_update(collection_with_sd: Collection[Comic], rss: RequestsMock) -> None:
    """When a modified pre-existing comic is added, the comic is updated."""
    comic_data: DiscordComic = {
        "title": "Sleepless Domain",
        "feed_url": "https://test-site.com/rss",
        "role_id": 581531863127031868,
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
    }
    update_result = add_to_collection(comic_data, collection_with_sd, HASH_SEED)
    assert isinstance(update_result, UpdateResult)
    assert update_result.matched_count == 1
    assert update_result.modified_count == 1
    assert len(rss.calls) == 0
    results = list(collection_with_sd.find({"title": comic_data["title"]}))
    assert len(results) == 1
    assert results[0]["feed_url"] == "https://test-site.com/rss"
    assert "last_entries" in results[0]


def test_invalid_rss(rss: RequestsMock) -> None:
    comic_data: DiscordComic = {
        "title": "Google",
        "feed_url": "https://google.com",
        "role_id": 581531863127031868,
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
    }
    rss.get(
        "https://google.com",
        status=200,
        body="""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"/><title>Google</title></head>
        <body>
            <h1>It's Google!</h1>
        </body>
        </html>
        """,
    )
    client: MongoClient[Comic] = MongoClient()
    collection = client.db.collection
    add_to_collection(comic_data, collection, HASH_SEED)
    comic = collection.find_one({"title": comic_data["title"]})
    assert comic is None
    print(comic)


def test_http_error(rss: RequestsMock) -> None:
    comic_data: DiscordComic = {
        "title": "Sleepless Domain",
        "feed_url": "https://sleeeeeeeepydomains.co/comic/rss",
        "role_id": 581531863127031868,
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
    }
    rss.get(
        "https://sleeeeeeeepydomains.co/comic/rss",
        status=404,
        body="""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"/><title>Google</title></head>
        <body>
            <h1>You fucked up!</h1>
        </body>
        </html>
        """,
    )
    client: MongoClient[Comic] = MongoClient()
    collection = client.db.collection
    with pytest.raises(HTTPError):
        add_to_collection(comic_data, collection, HASH_SEED)


example_feed = """
<?xml version="1.0" encoding="UTF-8" ?>\r\n\t<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\r\n\t<channel>\r\n\t\t<title>Sleepless Domain</title>\r\n\t\t<atom:link href="https://www.sleeplessdomain.com/comic/rss" rel="self" type="application/rss+xml" />
\r\n\t\t<link>https://www.sleeplessdomain.com/</link>\r\n\t\t<description>Latest Sleepless Domain comics and news</description>\r\n\t\t<language>en-us</language>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 22 - Page 2]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-22-page-2"><img src="https://www.sleeplessdomain.com/comicsthumbs/1695706790-0.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-22-page-2</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Tue, 26 Sep 2023 01:39:48 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-22-page-2</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 22 - Page 1]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-22-page-1"><img src="https://www.sleeplessdomain.com/comicsthumbs/1695150781-0.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-22-page-1</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Tue, 19 Sep 2023 15:12:58 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-22-page-1</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Interstitial]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-33"><img src="https://www.sleeplessdomain.com/comicsthumbs/1694458916-0.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-33</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Mon, 11 Sep 2023 15:01:54 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-33</guid>
</item>
</channel>
</rss>
"""  # noqa: E501
