"""Runs relevant end-to-end tests against the real Discord API."""

import json
import os
import re
import time
from collections.abc import Generator
from http import HTTPStatus
from time import sleep
from typing import TYPE_CHECKING

import pytest
import requests
import responses
from aioresponses import aioresponses
from bson import Int64, ObjectId
from dotenv import load_dotenv
from mongomock import MongoClient
from requests import PreparedRequest
from requests.structures import CaseInsensitiveDict
from responses import CallList, RequestsMock

from rss_to_webhook.check_feeds_and_update import (
    RateLimiter,
    daily_checks,
    regular_checks,
)
from rss_to_webhook.constants import DEFAULT_COLOR, HASH_SEED
from rss_to_webhook.db_types import Comic

if TYPE_CHECKING:
    from rss_to_webhook.discord_types import Message

# This file tries to use the real environment variables, so it can't be
# called in GitHub Actions.

# Loads the test environment variables
load_dotenv(".env.example")
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
THREAD_WEBHOOK_URL = os.environ["SD_WEBHOOK_URL"]
DAILY_WEBHOOK_URL = os.environ["DAILY_WEBHOOK_URL"]

# Loads the real environment variables
load_dotenv(override=True)
PASSTHROUGH_WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
PASSTHROUGH_DAILY_URL = os.environ["TEST2_WEBHOOK_URL"]
PASSTHROUGH_THREAD_ID = int(os.environ["TEST2_WEBHOOK_THREAD_ID"], base=10)


pytestmark = pytest.mark.side_effects


@pytest.fixture
def comic() -> Comic:
    return {
        "_id": ObjectId("612819b293b99b5809e18ab3"),
        "title": "Sleepless Domain",
        "feed_url": "http://www.sleeplessdomain.com/comic/rss",
        "role_id": Int64("581531863127031868"),
        "color": 11240119,
        "username": "KiwiFlea",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
        "feed_hash": b"*\xc5\x10O\xf3\xa1\x9f\xca5\x017\xdd\xf3\x8e\xe84",
        "last_entries": [
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-16",
                "published": "Fri, 21 Apr 2023 02:53:08 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-17",
                "published": "Sat, 29 Apr 2023 00:04:19 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-18",
                "published": "Sat, 06 May 2023 04:26:58 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-19",
                "published": "Sat, 13 May 2023 05:02:53 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-20",
                "published": "Sat, 20 May 2023 16:53:59 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-21",
                "published": "Sun, 28 May 2023 05:23:45 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-22",
                "published": "Sat, 03 Jun 2023 20:35:17 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-23",
                "published": "Sun, 11 Jun 2023 04:54:17 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-24",
                "published": "Sun, 18 Jun 2023 16:29:02 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-25",
                "published": "Mon, 26 Jun 2023 01:45:29 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-25-2",
                "published": "Mon, 03 Jul 2023 20:00:38 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-27",
                "published": "Wed, 12 Jul 2023 16:55:26 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-28",
                "published": "Fri, 28 Jul 2023 03:01:51 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-29",
                "published": "Wed, 09 Aug 2023 02:57:57 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-30",
                "published": "Sun, 20 Aug 2023 05:46:19 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-31",
                "published": "Fri, 25 Aug 2023 14:36:21 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-32",
                "published": "Sat, 02 Sep 2023 15:02:04 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-33",
                "published": "Mon, 11 Sep 2023 15:01:54 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-22-page-1",
                "published": "Tue, 19 Sep 2023 15:12:58 -0400",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
                "published": "Tue, 26 Sep 2023 01:39:48 -0400",
            },
        ],
        "dailies": [],
    }


@pytest.fixture
def minimal_comic() -> Comic:
    return {
        "_id": ObjectId("612819b293b99b5809e18ab3"),
        "title": "Sleepless Domain",
        "feed_url": "http://www.sleeplessdomain.com/comic/rss",
        "role_id": Int64("581531863127031868"),
        "feed_hash": b"*\xc5\x10O\xf3\xa1\x9f\xca5\x017\xdd\xf3\x8e\xe84",
        "last_entries": [
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-16",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-17",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-18",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-19",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-20",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-21",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-22",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-23",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-24",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-25",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-25-2",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-27",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-28",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-29",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-30",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-31",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-32",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-21-page-33",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-22-page-1",
            },
            {
                "link": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
            },
        ],
        "dailies": [],
    }


@pytest.fixture
def webhook() -> Generator[RequestsMock, None, None]:
    real_regular = f"{PASSTHROUGH_WEBHOOK_URL}?wait=true"
    real_daily = f"{PASSTHROUGH_DAILY_URL}?wait=true"
    real_thread = real_daily

    def relay_regular(
        request: PreparedRequest,
    ) -> tuple[int, CaseInsensitiveDict[str], str]:
        request.url = real_regular
        s = requests.Session()
        r = s.send(request)
        return (r.status_code, r.headers, r.text)

    def relay_daily(
        request: PreparedRequest,
    ) -> tuple[int, CaseInsensitiveDict[str], str]:
        request.url = real_daily
        s = requests.Session()
        r = s.send(request)
        return (r.status_code, r.headers, r.text)

    def relay_thread(
        request: PreparedRequest,
    ) -> tuple[int, CaseInsensitiveDict[str], str]:
        assert request.url
        request.url = re.sub(r"http.*?=true", real_thread, request.url)
        print(request.url)
        s = requests.Session()
        r = s.send(request)
        return (r.status_code, r.headers, r.text)

    with RequestsMock(assert_all_requests_are_fired=False) as responses:
        responses.add_passthru(real_regular)
        responses.add_passthru(real_daily)
        responses.add_callback(responses.POST, WEBHOOK_URL, callback=relay_regular)
        responses.add_callback(responses.POST, DAILY_WEBHOOK_URL, callback=relay_daily)
        responses.add_callback(
            responses.POST, THREAD_WEBHOOK_URL, callback=relay_thread
        )
        yield responses


@pytest.fixture
def rss() -> Generator[aioresponses, None, None]:
    with aioresponses() as mocked:
        mocked.get(
            "http://www.sleeplessdomain.com/comic/rss",
            status=200,
            body=example_feed,
            repeat=True,
        )
        yield mocked


@pytest.fixture
def measure_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleeps = []

    def log_sleep(delay: float) -> None:
        sleep(delay)
        sleeps.append(delay)

    monkeypatch.setattr(time, "sleep", log_sleep)
    return sleeps


@pytest.mark.usefixtures("rss")
def test_post_one_entry(comic: Comic, webhook: RequestsMock) -> None:
    """A comic with all attributes is posted."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["title"] = "test_post_one_update"
    comic["last_entries"].pop()  # One "new" entry
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert webhook.calls[0].request.body
    assert json.loads(webhook.calls[0].request.body) == {
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
        "content": "<@&581531863127031868>",
        "embeds": [{
            "color": 11240119,
            "description": "New test_post_one_update!",
            "title": "**Sleepless Domain - Chapter 22 - Page 2**",
            "url": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
        }],
        "username": "KiwiFlea",
    }


@pytest.mark.usefixtures("rss")
def test_minimal_one_entry(minimal_comic: Comic, webhook: RequestsMock) -> None:
    """A comic with no optional attributes is still posted."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    minimal_comic["title"] = "test_minimal_one_update"
    minimal_comic["last_entries"].pop()  # One "new" entry
    comics.insert_one(minimal_comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert webhook.calls[0].request.body
    assert json.loads(webhook.calls[0].request.body) == {
        "avatar_url": None,
        "content": "<@&581531863127031868>",
        "embeds": [{
            "color": DEFAULT_COLOR,
            "description": "New test_minimal_one_update!",
            "title": "**Sleepless Domain - Chapter 22 - Page 2**",
            "url": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
        }],
        "username": None,
    }


@pytest.mark.usefixtures("rss")
def test_post_two_entries(comic: Comic, webhook: RequestsMock) -> None:
    """When two new entries are found, they are both posted, from oldest to newest."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    num_new_entries = 2
    comic["title"] = "test_post_two_updates"
    # Remove the last two entries from the list
    del comic["last_entries"][-num_new_entries:]
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert webhook.calls[0].request.body
    embeds = json.loads(webhook.calls[0].request.body)["embeds"]
    assert embeds
    assert len(embeds) == num_new_entries
    assert embeds[0]["url"] == "https://www.sleeplessdomain.com/comic/chapter-22-page-1"
    assert embeds[1]["url"] == "https://www.sleeplessdomain.com/comic/chapter-22-page-2"


def get_embeds_by_message(calls: CallList) -> list[list[dict[str, str]]]:
    embeds = []
    for call in calls:
        assert call.request.body
        embeds.append(json.loads(call.request.body)["embeds"])
    return embeds


@pytest.mark.usefixtures("rss")
def test_post_many_entries(comic: Comic, webhook: RequestsMock) -> None:
    """When many new entries are found, they are posted in chunks of 10 per message."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["title"] = "test_post_all_new_updates"
    # No seen entries in feed
    comic["last_entries"] = [{"link": "https://comic.com/not-a-page"}]
    # The number of entries in the RSS feed
    num_new_entries = 20
    max_embeds_per_message = 10
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    embeds_by_message = get_embeds_by_message(webhook.calls)
    if len(embeds_by_message) > 1:
        assert all(
            len(embeds) == max_embeds_per_message for embeds in embeds_by_message[:-1]
        )
    assert all(len(embeds) <= max_embeds_per_message for embeds in embeds_by_message)
    all_embeds = [embed for embeds in embeds_by_message for embed in embeds]
    assert (
        all_embeds[0]["url"]
        == "https://www.sleeplessdomain.com/comic/chapter-21-page-16"
    )
    # Check that all 20 items in the RSS feed were posted
    assert len(all_embeds) == num_new_entries
    assert (
        all_embeds[-1]["url"]
        == "https://www.sleeplessdomain.com/comic/chapter-22-page-2"
    )


@pytest.mark.usefixtures("rss")
def test_thread_comic_new_entry(comic: Comic, webhook: RequestsMock) -> None:
    """Comics with a thread_id are posted in the appropriate thread."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["title"] = "test_thread_comic_new_entry"
    comic["last_entries"].pop()  # One new entry
    comic["thread_id"] = PASSTHROUGH_THREAD_ID
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert len(webhook.calls) == 2  # noqa: PLR2004


@pytest.mark.usefixtures("rss")
def test_daily_two_entries(comic: Comic, webhook: RequestsMock) -> None:
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["title"] = "test_daily_two_updates"
    comic["last_entries"].pop()  # One "new" entry
    comic["last_entries"].pop()  # Two "new" entries
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert webhook.calls[0].request.body
    regular_embeds = json.loads(webhook.calls[0].request.body)["embeds"]
    assert (
        regular_embeds[0]["url"]
        == "https://www.sleeplessdomain.com/comic/chapter-22-page-1"
    )
    assert (
        regular_embeds[1]["url"]
        == "https://www.sleeplessdomain.com/comic/chapter-22-page-2"
    )
    daily_checks(comics, DAILY_WEBHOOK_URL)
    assert webhook.calls[1].request.body
    daily_embeds = json.loads(webhook.calls[1].request.body)["embeds"]
    assert (
        daily_embeds[0]["url"]
        == "https://www.sleeplessdomain.com/comic/chapter-22-page-1"
    )
    assert (
        daily_embeds[1]["url"]
        == "https://www.sleeplessdomain.com/comic/chapter-22-page-2"
    )


@pytest.mark.benchmark
def test_daily_two_feeds(
    comic: Comic, rss: aioresponses, webhook: RequestsMock
) -> None:
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic2 = Comic(
        comic,
        _id=ObjectId("222222222222222222222222"),
        title="xkcd",
        last_entries=[],
        feed_url="https://xkcd.com/atom.xml",
    )  # type: ignore [misc]  # (mypy issue)[https://github.com/python/mypy/issues/8890]
    rss.get(
        "https://xkcd.com/atom.xml",
        status=200,
        headers={
            "ETag": '"f56-6062f676a7367-gzip"',
            "Last-Modified": "Wed, 27 Sep 2023 20:10:14 GMT",
        },
        body="""
        <feed xml:lang="en">
            <title>xkcd.com</title>
            <link href="https://xkcd.com/" rel="alternate"/>
            <id>https://xkcd.com/</id>
            <updated>2023-09-27T00:00:00Z</updated>
            <entry>
                <title>Book Podcasts</title>
                <link href="https://xkcd.com/2834/" rel="alternate"/>
                <updated>2023-09-27T00:00:00Z</updated>
                <id>https://xkcd.com/2834/</id>
            </entry>
        </feed>
        """,
    )
    comics.insert_one(comic2)
    comic["last_entries"].pop()  # One "new" entry
    comics.insert_one(comic)
    num_comics = 2
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert len(webhook.calls) == num_comics
    assert webhook.calls[0].request.body
    assert (
        json.loads(webhook.calls[0].request.body)["embeds"][0]["url"]
        == "https://www.sleeplessdomain.com/comic/chapter-22-page-2"
    )
    assert webhook.calls[1].request.body
    assert (
        json.loads(webhook.calls[1].request.body)["embeds"][0]["url"]
        == "https://xkcd.com/2834/"
    )
    webhook.calls.reset()
    daily_checks(comics, DAILY_WEBHOOK_URL)
    assert len(webhook.calls) == num_comics
    assert (
        json.loads(webhook.calls[0].request.body)["embeds"][0]["url"]
        == "https://www.sleeplessdomain.com/comic/chapter-22-page-2"
    )
    assert (
        json.loads(webhook.calls[1].request.body)["embeds"][0]["url"]
        == "https://xkcd.com/2834/"
    )


@pytest.mark.slow
@pytest.mark.usefixtures("webhook")
def test_pauses_at_hidden_rate_limit(
    comic: Comic, rss: aioresponses, measure_sleep: list[float]
) -> None:
    """The script avoids Discord's hidden webhook rate limit.

    Discord has a hidden rate limit of 30 messages to a webhook every 60
    seconds, as documented in [this tweet](https://twitter.com/lolpython/status/967621046277820416).

    Regression test for [99880a0](https://github.com/mymoomin/RSStoWebhook/commit/99880a040f5a3f365951836298555c06ea65a034).
    """
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"].pop()  # One "new" entry
    comic["feed_url"] = "http://www.sleeplessdomain.com/comic/short_rss"
    short_feed = """
    <?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel><title>Sleepless Domain</title>
    <link>https://www.sleeplessdomain.com/</link><description></description>
    <item>
        <title><![CDATA[Sleepless Domain - Chapter 22 - Page 2]]></title>
        <link>https://www.sleeplessdomain.com/comic/chapter-22-page-2</link>
        <pubDate>Tue, 26 Sep 2023 01:39:48 -0400</pubDate>
        <guid>https://www.sleeplessdomain.com/comic/chapter-22-page-2</guid>
    </item>
    </channel>
    </rss>
    """
    rss.get(
        "http://www.sleeplessdomain.com/comic/short_rss",
        status=200,
        body=short_feed,
        repeat=True,
    )
    # We need to post 30 times to hit the hidden ratelimit, and one more time to sleep
    duplicate_comics: list[Comic] = []
    for i in range(1, 32):
        # `ObjectId`s are 24 characters
        new_comic = Comic(
            comic,
            _id=ObjectId(f"{i:0>24}"),
            title=f"test_pauses_at_hidden_rate_limit {i:0>2}",
        )  # type: ignore [misc]  # (mypy issue)[https://github.com/python/mypy/issues/8890]
        duplicate_comics.append(new_comic)
    comics.insert_many(duplicate_comics)
    print(responses.registered())
    start = time.time()
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    end = time.time()
    main_duration = end - start
    assert len(measure_sleep) == 1
    assert measure_sleep[0] <= RateLimiter.fuzzed_window
    assert main_duration >= RateLimiter.fuzzed_window
    assert main_duration < 1.05 * RateLimiter.fuzzed_window


@pytest.mark.usefixtures("webhook")
def test_max_embeds() -> None:
    """A message can have at most 10 embeds."""
    too_long = {"embeds": [{"description": f"embed {i}"} for i in range(1, 11 + 1)]}
    bad_response = requests.post(
        WEBHOOK_URL,
        json=too_long,
        timeout=10,
        headers={"Accept-Encoding": "Identity"},
    )
    assert bad_response.status_code == HTTPStatus.BAD_REQUEST
    assert bad_response.json() == {
        "code": 50035,
        "errors": {
            "embeds": {
                "_errors": [{
                    "code": "BASE_TYPE_MAX_LENGTH",
                    "message": "Must be 10 or fewer in length.",
                }]
            }
        },
        "message": "Invalid Form Body",
    }
    at_limit = {"embeds": [{"description": f"embed {i}"} for i in range(1, 10 + 1)]}
    good_response = requests.post(
        WEBHOOK_URL,
        json=at_limit,
        timeout=10,
        headers={"Accept-Encoding": "Identity"},
    )
    assert good_response.status_code == HTTPStatus.OK


@pytest.mark.usefixtures("webhook")
def test_boundaries() -> None:
    too_long: Message = {
        "content": 2001 * "c",
        "avatar_url": f"https://{'i' * 64}.{'i' * 64}.{'i' * 64}/",
        "username": "n" * 81,
        "embeds": [{
            "color": 0xFFFFFF + 1,
            "description": 4097 * "d",
            "title": 257 * "t",
            "url": f"https://a.com?{(2048 - 12) * 'u'}",
        }],
    }
    longest: Message = {
        "content": 2000 * "c",
        "avatar_url": f"https://{'i' * 63}.{'i' * 63}.{'i' * 63}/",
        "username": "n" * 80,
        "embeds": [{
            "color": 0xFFFFFF,
            "description": 4096 * "d",
            "title": 256 * "t",
            "url": f"https://a.com?{(2048 - 15) * 'u'}",
        }],
    }
    shortest: Message = {
        "content": "",
        "avatar_url": "",
        "username": "u",
        "embeds": [{
            "color": 0,
            "description": "d",
            "title": "",
            "url": "",
        }],
    }
    too_short: Message = {
        "content": "",
        "avatar_url": "",
        "username": "",
        "embeds": [{
            "color": -1,
            "description": "",
            "title": "",
            "url": "",
        }],
    }
    all_nones = {
        "content": None,
        "avatar_url": None,
        "username": None,
        "embeds": [{
            "color": None,
            "description": None,
            "title": None,
            "url": None,
        }],
    }
    max_nones = {
        "content": None,
        "avatar_url": None,
        "username": None,
        "embeds": [{
            "color": None,
            "description": "d",
            "title": None,
            "url": None,
        }],
    }
    too_long_response = requests.post(
        WEBHOOK_URL,
        json=too_long,
        timeout=10,
        headers={"Accept-Encoding": "Identity"},
    )
    assert too_long_response.status_code == HTTPStatus.BAD_REQUEST
    assert too_long_response.json() == {
        "message": "Invalid Form Body",
        "code": 50035,
        "errors": {
            "content": {
                "_errors": [{
                    "code": "BASE_TYPE_MAX_LENGTH",
                    "message": "Must be 2000 or fewer in length.",
                }]
            },
            "embeds": {
                "0": {
                    "url": {
                        "_errors": [
                            {
                                "code": "BASE_TYPE_MAX_LENGTH",
                                "message": "Must be 2048 or fewer in length.",
                            },
                        ]
                    },
                    "title": {
                        "_errors": [{
                            "code": "BASE_TYPE_MAX_LENGTH",
                            "message": "Must be 256 or fewer in length.",
                        }]
                    },
                    "color": {
                        "_errors": [{
                            "code": "NUMBER_TYPE_MAX",
                            "message": (
                                "int value should be less than or equal to 16777215."
                            ),
                        }]
                    },
                    "description": {
                        "_errors": [{
                            "code": "BASE_TYPE_MAX_LENGTH",
                            "message": "Must be 4096 or fewer in length.",
                        }]
                    },
                }
            },
            "username": {
                "_errors": [{
                    "code": "BASE_TYPE_BAD_LENGTH",
                    "message": "Must be between 1 and 80 in length.",
                }]
            },
            "avatar_url": {
                "_errors": [{
                    "code": "URL_TYPE_INVALID_URL",
                    "message": "Not a well formed URL.",
                }]
            },
        },
    }
    longest_response = requests.post(
        WEBHOOK_URL,
        json=longest,
        timeout=10,
        headers={"Accept-Encoding": "Identity"},
    )
    assert longest_response.status_code == HTTPStatus.OK
    shortest_response = requests.post(
        WEBHOOK_URL,
        json=shortest,
        timeout=10,
        headers={"Accept-Encoding": "Identity"},
    )
    assert shortest_response.status_code == HTTPStatus.OK
    too_short_response = requests.post(
        WEBHOOK_URL,
        json=too_short,
        timeout=10,
        headers={"Accept-Encoding": "Identity"},
    )
    assert too_short_response.status_code == HTTPStatus.BAD_REQUEST
    assert too_short_response.json() == {
        "message": "Invalid Form Body",
        "code": 50035,
        "errors": {
            "embeds": {
                "0": {
                    "color": {
                        "_errors": [{
                            "code": "NUMBER_TYPE_MIN",
                            "message": (
                                "int value should be greater than or equal to 0."
                            ),
                        }]
                    }
                }
            },
            "username": {
                "_errors": [
                    {
                        "code": "BASE_TYPE_BAD_LENGTH",
                        "message": "Must be between 1 and 80 in length.",
                    },
                    {"code": "USERNAME_INVALID", "message": 'Username cannot be ""'},
                ]
            },
        },
    }
    all_nones_response = requests.post(
        WEBHOOK_URL,
        json=all_nones,
        timeout=10,
        headers={"Accept-Encoding": "Identity"},
    )
    assert all_nones_response.status_code == HTTPStatus.BAD_REQUEST
    assert all_nones_response.json() == {
        "message": "Invalid Form Body",
        "code": 50035,
        "errors": {
            "embeds": {
                "0": {
                    "description": {
                        "_errors": [{
                            "code": "BASE_TYPE_REQUIRED",
                            "message": "This field is required",
                        }]
                    }
                }
            }
        },
    }
    max_nones_response = requests.post(
        WEBHOOK_URL,
        json=max_nones,
        timeout=10,
        headers={"Accept-Encoding": "Identity"},
    )
    assert max_nones_response.status_code == HTTPStatus.OK


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
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 32]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-32"><img src="https://www.sleeplessdomain.com/comicsthumbs/1693681326-1.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-32</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Sat, 02 Sep 2023 15:02:04 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-32</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 31]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-31"><img src="https://www.sleeplessdomain.com/comicsthumbs/1692988583-0.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-31</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Fri, 25 Aug 2023 14:36:21 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-31</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 30]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-30"><img src="https://www.sleeplessdomain.com/comicsthumbs/1692524782-0.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-30</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Sun, 20 Aug 2023 05:46:19 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-30</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 29]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-29"><img src="https://www.sleeplessdomain.com/comicsthumbs/1691566235-0.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-29</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Wed, 09 Aug 2023 02:57:57 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-29</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 28]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-28"><img src="https://www.sleeplessdomain.com/comicsthumbs/1690527713-0.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-28</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Fri, 28 Jul 2023 03:01:51 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-28</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 27]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-27"><img src="https://www.sleeplessdomain.com/comicsthumbs/1689195335-0.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-27</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Wed, 12 Jul 2023 16:55:26 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-27</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 26]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-25-2"><img src="https://www.sleeplessdomain.com/comicsthumbs/1688428841-2.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-25-2</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Mon, 03 Jul 2023 20:00:38 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-25-2</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 25]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-25"><img src="https://www.sleeplessdomain.com/comicsthumbs/1687758337-site.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-25</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Mon, 26 Jun 2023 01:45:29 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-25</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 24]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-24"><img src="https://www.sleeplessdomain.com/comicsthumbs/1687239491-0.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-24</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Sun, 18 Jun 2023 16:29:02 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-24</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 23]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-23"><img src="https://www.sleeplessdomain.com/comicsthumbs/1686473660-0.jpg" /><br />New comic!</a><br />Today\'s News:<br /><!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN" "http://www.w3.org/TR/REC-html40/loose.dtd">\n<p><span style="color: rgb(255, 255, 255);">BG Pencils by&nbsp;</span><b style="color: rgb(255, 255, 255);"><a href="https://www.instagram.com/conniedaidone/?hl=en" target="_blank" style="color: rgb(76, 117, 143);">Connie Daidone</a></b><br></p>\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-23</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Sun, 11 Jun 2023 04:54:17 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-23</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 22]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-22"><img src="https://www.sleeplessdomain.com/comicsthumbs/1685838922-0.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-22</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Sat, 03 Jun 2023 20:35:17 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-22</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 21]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-21"><img src="https://www.sleeplessdomain.com/comicsthumbs/1685300709-0.jpg" /><br />New comic!</a><br />Today\'s News:<br /><!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN" "http://www.w3.org/TR/REC-html40/loose.dtd">\n<p><span style="color: rgb(255, 255, 255);">BG Pencils by&Acirc;&nbsp;</span><b style="color: rgb(255, 255, 255);"><a href="https://www.instagram.com/conniedaidone/?hl=en" target="_blank" style="color: rgb(76, 117, 143);">Connie Daidone</a></b><br></p>\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-21</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Sun, 28 May 2023 05:23:45 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-21</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 20]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-20"><img src="https://www.sleeplessdomain.com/comicsthumbs/1684616046-0.jpg" /><br />New comic!</a><br />Today\'s News:<br /><!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN" "http://www.w3.org/TR/REC-html40/loose.dtd">\n<p><span style="color: rgb(255, 255, 255);">BG Pencils by&nbsp;</span><b style="color: rgb(255, 255, 255);"><a href="https://www.instagram.com/conniedaidone/?hl=en" target="_blank" style="color: rgb(76, 117, 143);">Connie Daidone</a></b><br></p>\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-20</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Sat, 20 May 2023 16:53:59 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-20</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 19]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-19"><img src="https://www.sleeplessdomain.com/comicsthumbs/1684616114-0.jpg" /><br />New comic!</a><br />Today\'s News:<br /><!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN" "http://www.w3.org/TR/REC-html40/loose.dtd">\n<p><span style="color: rgb(255, 255, 255);">BG Pencils by&Acirc;&nbsp;</span><b style="color: rgb(255, 255, 255);"><a href="https://www.instagram.com/conniedaidone/?hl=en" target="_blank" style="color: rgb(76, 117, 143);">Connie Daidone</a></b><br></p>\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-19</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Sat, 13 May 2023 05:02:53 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-19</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 18]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-18"><img src="https://www.sleeplessdomain.com/comicsthumbs/1683361620-0.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-18</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Sat, 06 May 2023 04:26:58 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-18</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 17]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-17"><img src="https://www.sleeplessdomain.com/comicsthumbs/1682741061-sitepage.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-17</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Sat, 29 Apr 2023 00:04:19 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-17</guid>
</item>
<item>
    <title><![CDATA[Sleepless Domain - Chapter 21 - Page 16]]></title>
    <description><![CDATA[<a href="https://www.sleeplessdomain.com/comic/chapter-21-page-16"><img src="https://www.sleeplessdomain.com/comicsthumbs/1682059993-0.jpg" /><br />New comic!</a><br />Today\'s News:<br />\n]]></description>
    <link>https://www.sleeplessdomain.com/comic/chapter-21-page-16</link>
    <author>tech@thehiveworks.com</author>
    <pubDate>Fri, 21 Apr 2023 02:53:08 -0400</pubDate>
    <guid>https://www.sleeplessdomain.com/comic/chapter-21-page-16</guid>
</item>
</channel>
</rss>
"""  # noqa: E501
