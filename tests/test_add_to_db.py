from __future__ import annotations

import os
from typing import TYPE_CHECKING

import mmh3
import pytest
from bson import Int64, ObjectId
from dotenv import load_dotenv
from mongomock import Collection, MongoClient
from responses import RequestsMock

from rss_to_webhook.add_comic_to_database import ComicData, add_to_collection

if TYPE_CHECKING:
    from collections.abc import Generator

    from rss_to_webhook.db_types import Comic

load_dotenv()
HASH_SEED = int(os.environ["HASH_SEED"], 16)
WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
THREAD_WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]


@pytest.fixture()
def comic() -> ComicData:
    return {
        "title": "Sleepless Domain",
        "url": "http://www.sleeplessdomain.com/comic/rss",
        "role_id": Int64("581531863127031868"),
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
    }


@pytest.fixture()
def rss() -> Generator[RequestsMock, None, None]:
    with RequestsMock(assert_all_requests_are_fired=False) as responses:
        responses.get(
            "http://www.sleeplessdomain.com/comic/rss", status=200, body=example_feed
        )
        yield responses


@pytest.fixture()
def collection_with_sd() -> Collection[Comic]:
    client: MongoClient[Comic] = MongoClient()
    collection = client.db.collection
    comic: Comic = {
        "_id": ObjectId("111111111111111111111111"),
        "title": "Sleepless Domain",
        "url": "http://www.sleeplessdomain.com/comic/rss",
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


def test_add_valid_comic(rss: RequestsMock) -> None:
    """
    Tests that when a comic with a valid RSS feed is added to the database,
    it is inserted and the state of the rss feed is updated
    """
    client: MongoClient[Comic] = MongoClient()
    collection = client.db.collection
    comic_data: ComicData = {
        "title": "Sleepless Domain",
        "url": "http://www.sleeplessdomain.com/comic/rss",
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
        "url": "http://www.sleeplessdomain.com/comic/rss",
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


def test_no_changes(collection_with_sd: Collection[Comic], rss: RequestsMock) -> None:
    """
    Tests that when a comic that is already in the database is inserted again,
    with no change in any of the data, nothing is done
    """
    comic_data: ComicData = {
        "title": "Sleepless Domain",
        "url": "http://www.sleeplessdomain.com/comic/rss",
        "role_id": 581531863127031868,
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
    }
    update_result = add_to_collection(comic_data, collection_with_sd, HASH_SEED)
    assert update_result.matched_count == 1
    assert update_result.modified_count == 0
    assert len(rss.calls) == 0


def test_update(collection_with_sd: Collection[Comic], rss: RequestsMock) -> None:
    """
    Tests that when a comic that is already in the database is inserted again
    with different key values, those are updated, and the RSS state is preserved
    """
    comic_data: ComicData = {
        "title": "Sleepless Domain",
        "url": "https://test-site.com/rss",
        "role_id": 581531863127031868,
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
    }
    update_result = add_to_collection(comic_data, collection_with_sd, HASH_SEED)
    assert update_result.matched_count == 1
    assert update_result.modified_count == 1
    assert len(rss.calls) == 0
    results = list(collection_with_sd.find({"title": comic_data["title"]}))
    assert len(results) == 1
    assert results[0]["url"] == "https://test-site.com/rss"
    assert "last_entries" in results[0]


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
