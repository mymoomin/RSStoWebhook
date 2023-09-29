from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
import requests
import responses
from dotenv import load_dotenv
from pymongo import MongoClient
from requests import PreparedRequest

from rss_to_webhook.worker import main

if TYPE_CHECKING:
    from requests.structures import CaseInsensitiveDict

    from rss_to_webhook.db_types import Comic

load_dotenv()
WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
MONGODB_URI = os.environ["MONGODB_URI"]
HASH_SEED = int(os.environ["HASH_SEED"], 16)
client: MongoClient[Comic] = MongoClient(MONGODB_URI)


def relay_request(
    request: PreparedRequest,
) -> tuple[int, CaseInsensitiveDict[str], str]:
    request.url = WEBHOOK_URL
    s = requests.Session()
    r = s.send(request)
    return (r.status_code, r.headers, r.text)


@pytest.mark.skipif(
    "LOCAL" not in os.environ,
    reason="This test takes ages, so I don't want to run it on every commit",
)
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
