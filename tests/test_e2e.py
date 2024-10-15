import json
import os
import time
from collections.abc import Generator

import mmh3
import pytest
import responses
from aioresponses import aioresponses
from bson import Int64, ObjectId
from dotenv import load_dotenv
from mongomock import Collection, MongoClient
from requests import HTTPError
from responses import CallList, RequestsMock, matchers
from yarl import URL

from rss_to_webhook import constants
from rss_to_webhook.check_feeds_and_update import (
    RateLimiter,
    daily_checks,
    regular_checks,
)
from rss_to_webhook.constants import HASH_SEED
from rss_to_webhook.db_types import Comic

load_dotenv(".env.example")
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
THREAD_WEBHOOK_URL = os.environ["SD_WEBHOOK_URL"]
DAILY_WEBHOOK_URL = os.environ["DAILY_WEBHOOK_URL"]


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
def webhook() -> Generator[RequestsMock, None, None]:
    with RequestsMock(assert_all_requests_are_fired=False) as responses:
        responses.post(
            WEBHOOK_URL,
            status=200,
            headers={
                "x-ratelimit-limit": "5",
                "x-ratelimit-remaining": "4",
                "x-ratelimit-reset-after": "0.399",
            },
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
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    def nothing(_time: float) -> None:
        pass

    monkeypatch.setattr(time, "sleep", nothing)


@pytest.fixture
def measure_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleeps = []

    def log_sleep(time: float) -> None:
        sleeps.append(time)

    monkeypatch.setattr(time, "sleep", log_sleep)
    return sleeps


@pytest.mark.usefixtures("_no_sleep")
def test_no_sleep() -> None:
    start = time.time()
    time.sleep(10)
    end = time.time()
    assert end - start < 1


@pytest.mark.usefixtures("_no_sleep")
def test_mongo_mock(comic: Comic) -> None:
    comics: Collection[Comic] = MongoClient().db.collection  # type: ignore [assignment]
    comics.insert_one(comic)
    assert comic == comics.find_one({"_id": ObjectId("612819b293b99b5809e18ab3")})


@pytest.mark.usefixtures("_no_sleep")
def test_post_no_update(comic: Comic, rss: aioresponses, webhook: RequestsMock) -> None:
    """The script doesn't post to the webhook when no new updates are found."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comics.insert_one(comic)
    regular_checks(comics, constants.HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert len(webhook.calls) == 0


@pytest.mark.usefixtures("_no_sleep")
def test_store_no_update(
    comic: Comic, rss: aioresponses, webhook: RequestsMock
) -> None:
    """Only caching information is updated when no new updates are found."""
    rss.get(
        "http://www.sleeplessdomain.com/comic/rss_with_headers",
        status=200,
        body=example_feed,
        headers={
            "ETag": '"f56-6062f676a7367-gzip"',
            "Last-Modified": "Wed, 27 Sep 2023 20:10:14 GMT",
        },
    )
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["feed_url"] = "http://www.sleeplessdomain.com/comic/rss_with_headers"
    caching_info = {
        "feed_hash": mmh3.hash_bytes(example_feed, HASH_SEED),
        "etag": '"f56-6062f676a7367-gzip"',
        "last_modified": "Wed, 27 Sep 2023 20:10:14 GMT",
    }
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    updated_comic = comics.find_one({"_id": comic["_id"]})
    assert updated_comic
    assert comic | caching_info == updated_comic


@pytest.mark.usefixtures("_no_sleep")
def test_hash_match(comic: Comic, rss: aioresponses, webhook: RequestsMock) -> None:
    """The script does nothing when the feed's hash matches the previous hash."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"].pop()  # One new entry
    comic["feed_hash"] = mmh3.hash_bytes(
        example_feed, HASH_SEED
    )  # But the hash is the same
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert len(webhook.calls) == 0


@pytest.mark.usefixtures("_no_sleep")
def test_post_one_update(
    comic: Comic, rss: aioresponses, webhook: RequestsMock
) -> None:
    """The script posts the correct information when one new update is found."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"].pop()  # One "new" entry
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert webhook.calls[0].request.body
    assert json.loads(webhook.calls[0].request.body) == {
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
        "content": "<@&581531863127031868>",
        "embeds": [{
            "color": 11240119,
            "description": "New Sleepless Domain!",
            "title": "**Sleepless Domain - Chapter 22 - Page 2**",
            "url": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
        }],
        "username": "KiwiFlea",
    }


@pytest.mark.usefixtures("_no_sleep")
def test_store_one_update(
    comic: Comic, rss: aioresponses, webhook: RequestsMock
) -> None:
    """When one new update is found, it is stored in the database."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"].pop()  # One "new" entry
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    updated_comic = comics.find_one({"_id": comic["_id"]})
    assert updated_comic
    assert updated_comic["last_entries"][-1] == {
        "title": "Sleepless Domain - Chapter 22 - Page 2",
        "link": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
        "published": "Tue, 26 Sep 2023 01:39:48 -0400",
        "id": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
    }


@pytest.mark.usefixtures("_no_sleep")
def test_post_two_updates(
    comic: Comic, rss: aioresponses, webhook: RequestsMock
) -> None:
    """When two new updates are found, they are both posted, from oldest to newest.

    Regression test for [#2](https://github.com/mymoomin/RSStoWebhook/issues/2)
    """
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    num_new_entries = 2
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


@pytest.mark.usefixtures("_no_sleep")
def test_store_two_updates(
    comic: Comic, rss: aioresponses, webhook: RequestsMock
) -> None:
    """When there are two new updates, they are stored in the database."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    num_new_entries = 2
    # Remove the last two entries from the list
    del comic["last_entries"][-num_new_entries:]
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    updated_comic = comics.find_one({"_id": comic["_id"]})
    assert updated_comic
    assert [entry["link"] for entry in updated_comic["last_entries"][-2:]] == [
        "https://www.sleeplessdomain.com/comic/chapter-22-page-1",
        "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
    ]


@pytest.mark.usefixtures("_no_sleep")
def test_idempotence(comic: Comic, rss: aioresponses, webhook: RequestsMock) -> None:
    """The script will not post the same update twice."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"].pop()  # One "new" entry
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert len(webhook.calls) == 1  # One post
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert len(webhook.calls) == 1  # Still one post


@pytest.mark.usefixtures("_no_sleep")
@pytest.mark.benchmark
def test_suddenly_pubdates(
    comic: Comic, rss: aioresponses, webhook: RequestsMock
) -> None:
    """When an RSS feed adds <pubDate>s to all entries, old entries are not reposted.

    There is a logic error where this currently appears to work until the check
    one after a new entry is found and posted, at which point every old entry
    is posted.
    """
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"].pop()  # One "new" entry
    comic["last_entries"] = [{"link": entry["link"]} for entry in comic["last_entries"]]
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert len(webhook.calls) == 1  # One post
    assert webhook.calls[0].request.body
    assert len(json.loads(webhook.calls[0].request.body)["embeds"]) == 1
    comics.update_one({"_id": comic["_id"]}, {"$set": {"feed_hash": b"hi!"}})
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert len(webhook.calls) == 1  # Still one post


def get_embeds_by_message(calls: CallList) -> list[list[dict[str, str]]]:
    embeds = []
    for call in calls:
        assert call.request.body
        embeds.append(json.loads(call.request.body)["embeds"])
    return embeds


@pytest.mark.usefixtures("_no_sleep")
def test_post_all_new_updates(
    comic: Comic, rss: aioresponses, webhook: RequestsMock
) -> None:
    """The script works when all updates are new and there are many of them.

    Regression test for [e33e902](https://github.com/mymoomin/RSStoWebhook/commit/e33e902cbf8d7a1ce4e5bb096386ca6e70469921)
    """
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
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


@pytest.mark.usefixtures("_no_sleep")
def test_store_all_new_updates(
    comic: Comic, rss: aioresponses, webhook: RequestsMock
) -> None:
    """When there are many new updates, they are all stored in the database.

    Regression test for [e33e902](https://github.com/mymoomin/RSStoWebhook/commit/e33e902cbf8d7a1ce4e5bb096386ca6e70469921)
    """
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    # No seen entries in feed
    comic["last_entries"] = []
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    updated_comic = comics.find_one({"_id": comic["_id"]})
    assert updated_comic
    last_entries = updated_comic["last_entries"]
    assert (
        last_entries[0]["link"]
        == "https://www.sleeplessdomain.com/comic/chapter-21-page-16"
    )
    # Check that all 20 items in the RSS feed were posted
    assert len(last_entries) == 20  # noqa: PLR2004
    assert (
        last_entries[-1]["link"]
        == "https://www.sleeplessdomain.com/comic/chapter-22-page-2"
    )


@pytest.mark.usefixtures("_no_sleep")
def test_caching_match(comic: Comic, rss: aioresponses, webhook: RequestsMock) -> None:
    """Caching headers in responses are stored, and are used in the next run."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["title"] = "xkcd"
    comic["last_entries"] = [{"link": "https://xkcd.com/2834/"}]
    comic["feed_url"] = "https://xkcd.com/atom.xml"
    comics.insert_one(comic)
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
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    new_comic = comics.find_one({"title": "xkcd"})
    assert new_comic
    assert "etag" in new_comic
    assert "last_modified" in new_comic
    rss.get(
        "https://xkcd.com/atom.xml",
        status=304,
        headers={
            "ETag": '"f56-6062f676a7367-gzip"',
            "Last-Modified": "Wed, 27 Sep 2023 20:10:14 GMT",
        },
    )
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    print(list(rss.requests.keys()))
    req = rss.requests["GET", URL("https://xkcd.com/atom.xml")][-1]
    h = req.kwargs["headers"]
    assert h == h | {
        "If-None-Match": '"f56-6062f676a7367-gzip"',
        "If-Modified-Since": "Wed, 27 Sep 2023 20:10:14 GMT",
    }  # Tests headers includes these values


@pytest.mark.usefixtures("_no_sleep")
def test_handles_rss_errors(
    comic: Comic, rss: aioresponses, webhook: RequestsMock
) -> None:
    """If one feed has a connection error, other feeds work as normal."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"].pop()  # One new entry
    bad_comic = Comic(
        comic,
        _id=ObjectId("6129798080ead12f9ac5dbbc"),
        feed_url="http://does.not.exist/nowhere",
    )  # type: ignore [misc]  # (mypy issue)[https://github.com/python/mypy/issues/8890]
    rss.get("http://does.not.exist/nowhere", status=404)
    comics.insert_many([bad_comic, comic])
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert len(webhook.calls) == 1


def test_updates_error_count(comic: Comic, rss: aioresponses) -> None:
    """If there is an error connecting to an RSS feed, it is tracked."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    bad_comic = Comic(
        comic,
        _id=ObjectId("6129798080ead12f9ac5dbbc"),
        feed_url="http://does.not.exist/nowhere",
    )  # type: ignore [misc]  # (mypy issue)[https://github.com/python/mypy/issues/8890]
    rss.get("http://does.not.exist/nowhere", status=404)
    comics.insert_many([bad_comic, comic])
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    updated_good_comic = comics.find_one({"_id": comic["_id"]})
    assert updated_good_comic
    assert updated_good_comic.get("error_count") in {0, None}
    updated_bad_comic = comics.find_one({"_id": bad_comic["_id"]})
    assert updated_bad_comic
    assert "error_count" in updated_bad_comic
    assert updated_bad_comic["error_count"] == 1
    errors = updated_bad_comic.get("errors")
    assert errors
    assert len(errors) == 1
    assert "ClientResponseError: 404" in errors[0]


@responses.activate()
@pytest.mark.usefixtures("_no_sleep")
def test_thread_comic_new_entry(comic: Comic, rss: aioresponses) -> None:
    """Comics with a thread_id are posted in the appropriate thread."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"].pop()  # One new entry
    comic["thread_id"] = 932666606000164965
    normal_webhook = responses.post(
        WEBHOOK_URL,
        status=204,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "4",
            "x-ratelimit-reset-after": "0.399",
        },
    )
    thread_webhook = responses.post(
        THREAD_WEBHOOK_URL,
        status=204,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "4",
            "x-ratelimit-reset-after": "0.399",
        },
        match=[
            matchers.query_param_matcher(
                {"thread_id": 932666606000164965},
                strict_match=False,
            )
        ],
    )
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert normal_webhook.call_count == 1
    assert thread_webhook.call_count == 1


@responses.activate()
@pytest.mark.usefixtures("_no_sleep")
def test_thread_comic_many_entries(comic: Comic, rss: aioresponses) -> None:
    """Comics with a thread_id are posted in the appropriate thread."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"] = comic["last_entries"][:-15]  # 15 new entries
    comic["thread_id"] = 932666606000164965
    normal_webhook = responses.post(
        WEBHOOK_URL,
        status=204,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "4",
            "x-ratelimit-reset-after": "0.399",
        },
    )
    thread_webhook = responses.post(
        THREAD_WEBHOOK_URL,
        status=204,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "4",
            "x-ratelimit-reset-after": "0.399",
        },
        match=[
            matchers.query_param_matcher(
                {"thread_id": 932666606000164965},
                strict_match=False,
            )
        ],
    )
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert normal_webhook.call_count == 2  # noqa: PLR2004
    assert thread_webhook.call_count == 2  # noqa: PLR2004


@responses.activate()
@pytest.mark.usefixtures("_no_sleep")
def test_thread_comic_body(comic: Comic, rss: aioresponses) -> None:
    """Comics with a thread_id have the correct body. In particular, no content."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"].pop()  # One new entry
    comic["thread_id"] = 932666606000164965
    responses.post(
        WEBHOOK_URL,
        status=204,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "4",
            "x-ratelimit-reset-after": "0.399",
        },
    )
    responses.post(
        THREAD_WEBHOOK_URL,
        status=204,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "4",
            "x-ratelimit-reset-after": "0.399",
        },
        match=[
            matchers.query_param_matcher(
                {"thread_id": 932666606000164965},
                strict_match=False,
            )
        ],
    )
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    # The second `post` was to the thread
    assert responses.calls[1].request.body
    assert json.loads(responses.calls[1].request.body) == {
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
        "embeds": [{
            "color": 11240119,
            "description": "New Sleepless Domain!",
            "title": "**Sleepless Domain - Chapter 22 - Page 2**",
            "url": "https://www.sleeplessdomain.com/comic/chapter-22-page-2",
        }],
        "username": "KiwiFlea",
    }


def test_daily_two_updates(
    comic: Comic, rss: aioresponses, webhook: RequestsMock
) -> None:
    """The script maintains order when posting daily updates.

    Regression test for [#2](https://github.com/mymoomin/RSStoWebhook/issues/2)
    """
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
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
    daily_checks(comics, WEBHOOK_URL)
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
def test_daily_ordering(comic: Comic, rss: aioresponses, webhook: RequestsMock) -> None:
    """Comics are checking in alphabetical order."""
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
    daily_checks(comics, WEBHOOK_URL)
    assert len(webhook.calls) == num_comics
    assert (
        json.loads(webhook.calls[0].request.body)["embeds"][0]["url"]
        == "https://www.sleeplessdomain.com/comic/chapter-22-page-2"
    )
    assert (
        json.loads(webhook.calls[1].request.body)["embeds"][0]["url"]
        == "https://xkcd.com/2834/"
    )


def test_daily_idempotent(
    comic: Comic, rss: aioresponses, webhook: RequestsMock
) -> None:
    """The script posts daily updates exactly once."""
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["dailies"].append(comic["last_entries"][-1])  # One "new" entry
    comics.insert_one(comic)
    daily_checks(comics, WEBHOOK_URL)
    assert webhook.calls[0].request.body
    assert (
        json.loads(webhook.calls[0].request.body)["embeds"][0]["url"]
        == "https://www.sleeplessdomain.com/comic/chapter-22-page-2"
    )
    assert len(webhook.calls) == 1
    daily_checks(comics, WEBHOOK_URL)
    assert len(webhook.calls) == 1


@responses.activate()
@pytest.mark.slow  # This is already tested in test_ratelimiter.py
def test_pauses_only_at_rate_limit(
    comic: Comic, rss: aioresponses, measure_sleep: list[float]
) -> None:
    """The script sleeps until the rate-limiting window is over when it is exhausted.

    Also tests that the script doesn't sleep when the rate-limiting window has space.

    Regression test for [99880a0](https://github.com/mymoomin/RSStoWebhook/commit/99880a040f5a3f365951836298555c06ea65a034)
    """
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"].pop()  # One "new" entry
    # We need to post twice in order to sleep
    comic2 = Comic(comic, _id=ObjectId("222222222222222222222222"))  # type: ignore [misc]  # (mypy issue)[https://github.com/python/mypy/issues/8890]
    # The third time shouldn't sleep at all
    comic3 = Comic(comic, _id=ObjectId("333333333333333333333333"))  # type: ignore [misc]
    comics.insert_many([comic, comic2, comic3])
    responses.post(
        WEBHOOK_URL,
        status=200,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset-after": "1",
        },
    )
    responses.post(
        WEBHOOK_URL,
        status=200,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "1",
            "x-ratelimit-reset-after": "1",
        },
    )
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert len(measure_sleep) == 1
    assert measure_sleep[0] == 1


@responses.activate()
@pytest.mark.slow  # This is already tested in test_ratelimiter.py
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
    for i in range(31):
        # `ObjectId`s are 24 characters
        new_comic = Comic(comic, _id=ObjectId(f"{i:0>24}"))  # type: ignore [misc]  # (mypy issue)[https://github.com/python/mypy/issues/8890]
        duplicate_comics.append(new_comic)
    comics.insert_many(duplicate_comics)
    responses.post(
        WEBHOOK_URL,
        status=200,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "1",
            "x-ratelimit-reset-after": "1",
        },
    )
    print(responses.registered())
    start = time.time()
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    end = time.time()
    main_duration = end - start
    assert len(measure_sleep) == 1
    assert measure_sleep[0] <= RateLimiter.fuzzed_window
    assert main_duration + measure_sleep[0] >= RateLimiter.fuzzed_window
    assert main_duration + measure_sleep[0] < RateLimiter.fuzzed_window + 1


@responses.activate()
@pytest.mark.usefixtures("_no_sleep")
@pytest.mark.slow  # This is already tested in test_ratelimiter.py
def test_fails_on_429(comic: Comic, rss: aioresponses) -> None:
    """The script fails with an exception when it exceeds the rate limit.

    In the future this should be set to email me
    """
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"].pop()  # One "new" entry
    comics.insert_one(comic)
    responses.post(
        WEBHOOK_URL,
        status=429,
        headers={
            "retry-after": "1",
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "4",
            "x-ratelimit-reset-after": "0.399",
            "x-ratelimit-scope": "shared",
        },
        json={
            "message": "The resource is being rate limited.",
            "retry_after": 0.529,
            "global": False,
        },
    )
    with pytest.raises(HTTPError) as e:
        regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert "429" in str(e.value)


@responses.activate()
@pytest.mark.usefixtures("_no_sleep")
def test_no_update_on_failure(comic: Comic, rss: aioresponses) -> None:
    """The script does not update caching headers when the webhook gives errors.

    Regression test for [No Commit]
    """
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    entry_url = comic["last_entries"].pop()  # One "new" entry
    comic["feed_url"] = "https://www.questionablecontent.net/QCRSS.xml"
    comics.insert_one(comic)
    rss.get(
        "https://www.questionablecontent.net/QCRSS.xml",
        status=200,
        body=example_feed,
        headers={
            "ETag": '"f56-6062f676a7367-gzip"',
            "Last-Modified": "Wed, 27 Sep 2023 20:10:14 GMT",
        },
    )
    responses.post(
        WEBHOOK_URL,
        status=429,
        headers={
            "retry-after": "1",
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "4",
            "x-ratelimit-reset-after": "0.399",
            "x-ratelimit-scope": "shared",
        },
        json={
            "message": "The resource is being rate limited.",
            "retry_after": 0.529,
            "global": False,
        },
    )
    with pytest.raises(HTTPError):
        regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    new_comic = comics.find_one({"_id": comic["_id"]})
    assert new_comic
    assert "last_modified" not in new_comic
    assert "etag" not in new_comic
    assert comic["feed_hash"] != mmh3.hash_bytes(example_feed, HASH_SEED)
    assert entry_url not in comic["last_entries"]


@responses.activate()
@pytest.mark.usefixtures("_no_sleep")
def test_no_crash_on_missing_headers(comic: Comic, rss: aioresponses) -> None:
    """The script does not crash when webhook response headers are missing.

    Regression test for [b0939df](https://github.com/mymoomin/RSStoWebhook/commit/b0939df99bd28ed17d69e814cf51bb725fc97883)
    """
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comic["last_entries"].pop()  # One "new" entry
    comics.insert_one(comic)
    responses.post(WEBHOOK_URL, status=200, headers={})
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)


@pytest.mark.usefixtures("_no_sleep")
def test_user_agent(comic: Comic, rss: aioresponses) -> None:
    """The user agent is set from `constants.CUSTOM_USER_AGENT`.

    Regression test for [192de2b](https://github.com/mymoomin/RSStoWebhook/commit/192de2b456810174aa09b6feac6a7b05f695a001)
    and [c45d8b7](https://github.com/mymoomin/RSStoWebhook/commit/c45d8b7a8cdb3507f0a407f2e453e1ebde284e14)
    """
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    comics.insert_one(comic)
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    request = rss.requests["GET", URL(comic["feed_url"])][0]
    assert request
    headers = request.kwargs["headers"]
    assert headers["User-Agent"] == constants.CUSTOM_USER_AGENT


@pytest.mark.benchmark
@pytest.mark.slow
def test_performance(
    comic: Comic, rss: aioresponses, webhook: RequestsMock, measure_sleep: list[float]
) -> None:
    client: MongoClient[Comic] = MongoClient()
    comics = client.db.collection
    last_entries = comic["last_entries"]
    num_entries = len(last_entries)  # Currently 20
    duplicate_comics: list[Comic] = []
    for i in range(num_entries):
        pop_new = Comic(
            comic,
            _id=ObjectId(f"a{i:0>23}"),  # `ObjectId`s are 24 characters
            last_entries=last_entries[:i],
            title=f"pop_new {i:0>2}",
        )  # type: ignore [misc]  # (mypy issue)[https://github.com/python/mypy/issues/8890]
        duplicate_comics.append(pop_new)
        pop_old = Comic(
            comic,
            _id=ObjectId(f"b{i:0>23}"),
            last_entries=last_entries[i + 1 :],
            title=f"pop_old {i:0>2}",
        )  # type: ignore [misc]
        duplicate_comics.append(pop_old)
        pop_one = Comic(
            comic,
            _id=ObjectId(f"c{i:0>23}"),
            title=f"pop_one {i:0>2}",
            last_entries=last_entries[:i] + last_entries[i + 1 :],
        )  # type: ignore [misc]
        duplicate_comics.append(pop_one)
        keep_one = Comic(
            comic,
            _id=ObjectId(f"d{i:0>23}"),
            last_entries=[last_entries[i]],
            title=f"keep_one {i:0>2}",
        )  # type: ignore [misc]
        duplicate_comics.append(keep_one)
    comics.insert_many(duplicate_comics)
    webhook.post(
        THREAD_WEBHOOK_URL,
        status=200,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "2",
            "x-ratelimit-reset-after": "1",
        },
    )
    daily = webhook.post(
        DAILY_WEBHOOK_URL,
        status=200,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "2",
            "x-ratelimit-reset-after": "1",
        },
    )
    print(responses.registered())
    start = time.time()
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    end = time.time()
    main_duration = end - start
    print(main_duration)
    assert len(measure_sleep) == (len(webhook.calls) - 1) // 30
    webhook.calls.reset()
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    assert len(webhook.calls) == 0
    start = time.time()
    daily_checks(comics, DAILY_WEBHOOK_URL)
    end = time.time()
    daily_duration = end - start
    print(daily_duration)
    assert len(measure_sleep) == 2 * ((len(webhook.calls) - 1) // 30)
    daily.calls.reset()
    daily_checks(comics, DAILY_WEBHOOK_URL)
    assert daily.call_count == 0


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
