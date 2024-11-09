from __future__ import annotations

import os
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
import requests
import responses
from dotenv import load_dotenv
from pymongo import MongoClient
from requests import PreparedRequest

from rss_to_webhook.check_feeds_and_update import regular_checks
from rss_to_webhook.constants import HASH_SEED

if TYPE_CHECKING:
    from requests.structures import CaseInsensitiveDict

    from rss_to_webhook.db_types import Comic


# This file tries to use the real environment variables, so it can't be
# called in GitHub Actions.
load_dotenv(override=True)
WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
THREAD_WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
MONGODB_URI = os.environ["MONGODB_URI"]
DB_NAME = os.environ["DB_NAME"]


def relay_request(
    request: PreparedRequest,
) -> tuple[int, CaseInsensitiveDict[str], str]:
    request.url = f"{WEBHOOK_URL}?wait=true"
    s = requests.Session()
    r = s.send(request)
    print(r.status_code)
    return (r.status_code, r.headers, r.text)


@pytest.mark.side_effects
@responses.activate()
def test_fully() -> None:
    """When called in a production environment, everything behaves as expected."""
    responses.add_passthru(WEBHOOK_URL)
    client: MongoClient[Comic] = MongoClient(MONGODB_URI)
    # Not the actual comics
    comics = client[DB_NAME]["test-comics"]
    # Get everything up to date
    regular_checks(comics, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
    # Place every comic one entry behind present
    res = comics.update_many({}, {"$pop": {"last_entries": 1}})
    num_comics = res.modified_count
    # Unset last modified
    comics.update_many({}, {"$unset": {"last_modified": ""}})
    # Set hash to something fake
    comics.update_many({}, {"$set": {"feed_hash": b"hello there!"}})
    # Set etag to something fake if it exists
    comics.update_many({"etag": {"$exists": True}}, {"$set": {"etag": '"hi!"'}})
    # Fuck with the url so we can instrument it slightly
    fake_url = "https://discord.com/api/v8/webhooks/837330400841826375/testing"
    responses.add_callback(responses.POST, fake_url, callback=relay_request)
    print("added callback")
    regular_checks(comics, HASH_SEED, fake_url, THREAD_WEBHOOK_URL)
    print("redone checks")
    # One update posted per comic
    assert len(responses.calls) == num_comics
    # All posted correctly
    assert all(call.response.status_code == HTTPStatus.OK for call in responses.calls)  # type: ignore[reportAttributeAccessIssue, union-attr]
    regular_checks(comics, HASH_SEED, fake_url, THREAD_WEBHOOK_URL)
    assert len(responses.calls) == num_comics  # Nothing changed, so no new updates
    # All our fake values have been changed
    assert (
        comics.find_one({"$or": [{"feed-hash": b"hello there"}, {"etag": '"hi!"'}]})
        is None
    )
    # The rss feeds with a Last-Modified header have had that saved
    assert comics.find_one({"last_modified": {"$exists": True}})
