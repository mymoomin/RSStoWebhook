from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

import pytest
import requests
import responses
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from requests import PreparedRequest

from rss_to_webhook.worker import RateLimitState, main, post

if TYPE_CHECKING:
    from feedparser.util import Entry
    from requests.structures import CaseInsensitiveDict

    from rss_to_webhook.db_types import Comic

load_dotenv()
WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
MONGODB_URI = os.environ["MONGODB_URI"]
HASH_SEED = int(os.environ["HASH_SEED"], 16)


def relay_request(
    request: PreparedRequest,
) -> tuple[int, CaseInsensitiveDict[str], str]:
    request.url = WEBHOOK_URL
    s = requests.Session()
    r = s.send(request)
    return (r.status_code, r.headers, r.text)


@pytest.mark.slow()
@responses.activate()
def test_fully() -> None:
    """
    Test asserts that when called in a production environment, everything
    behaves as expected
    """
    responses.add_passthru(WEBHOOK_URL)
    client: MongoClient[Comic] = MongoClient(MONGODB_URI)
    # Not the actual comics
    comics = client["discord_rss"]["test_comics"]
    # Get everything up to date
    main(comics, HASH_SEED, WEBHOOK_URL)
    # Place every comic one entry behind present
    res = comics.update_many({}, {"$pop": {"last_entries": 1}})
    num_comics = res.modified_count
    # Unset last modified
    comics.update_many({}, {"$unset": {"last_modified": ""}})
    # Set hash to something fake
    comics.update_many({}, {"$set": {"hash": b"hello there!"}})
    # Set etag to something fake if it exists
    comics.update_many({"etag": {"$exists": True}}, {"$set": {"etag": '"hi!"'}})
    # Fuck with the url so we can instrument it slightly
    fake_url = "https://discord.com/api/v8/webhooks/837330400841826375/testing"
    responses.add_callback(responses.POST, fake_url, callback=relay_request)
    print("added callback")
    main(comics, HASH_SEED, fake_url)
    print("redone checks")
    assert len(responses.calls) == num_comics  # One update posted per comic
    main(comics, HASH_SEED, fake_url)
    assert len(responses.calls) == num_comics  # Nothing changed, so no new updates
    # All our fake values have been changed
    assert (
        comics.find_one({"$or": [{"hash": b"hello there"}, {"etag": '"hi!"'}]}) is None
    )
    # The rss feeds with a Last-Modified header have had that saved
    assert comics.find_one({"last_modified": {"$exists": True}})


@pytest.mark.slow()
def test_real_rate_limit() -> None:
    """
    Tests that when the script makes many posts at once, it respects the rate limits

    This is a regression test for [01fd62b](https://github.com/mymoomin/RSStoWebhook/commit/01fd62be50918775b68bedbb71c1f4b5ec148acf)
    """
    comic: Comic = {
        "_id": ObjectId("111111111111111111111111"),
        "name": "Test Webcomic",
        "url": "https://example.com/",
        "last_entries": [],
        "hash": b"",
    }
    entries: list[Entry] = [
        {"title": str(i), "link": f"https://example.com/{i}/"}
        for i in range(59)  # Sleeps once and stops just before sleep 2
    ]
    state = RateLimitState(1, time.time())
    post(WEBHOOK_URL, comic, entries, state)