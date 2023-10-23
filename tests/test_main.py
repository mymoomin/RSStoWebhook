from __future__ import annotations

import os
from typing import TYPE_CHECKING

import mongomock
import pytest
from dotenv import load_dotenv

from rss_to_webhook import check_feeds_and_update
from rss_to_webhook.check_feeds_and_update import main
from rss_to_webhook.constants import DEFAULT_AIOHTTP_TIMEOUT, HASH_SEED

if TYPE_CHECKING:
    from aiohttp import ClientTimeout
    from pymongo.collection import Collection

    from rss_to_webhook.db_types import Comic

load_dotenv(".env.example")
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
THREAD_WEBHOOK_URL = os.environ["SD_WEBHOOK_URL"]
DAILY_WEBHOOK_URL = os.environ["DAILY_WEBHOOK_URL"]
TEST_WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture()
def _fake_env(monkeypatch: pytest.MonkeyPatch) -> None:
    print("_fake_env")
    real_load = load_dotenv

    def load_example_env() -> None:
        print("called load_example_env")
        real_load(".env.example")

    monkeypatch.setattr(check_feeds_and_update, "load_dotenv", load_example_env)
    print("set _fake_env")


@pytest.fixture()
def fake_db(monkeypatch: pytest.MonkeyPatch) -> mongomock.MongoClient[Comic]:
    print("hiiiii")
    client: mongomock.MongoClient[Comic] = mongomock.MongoClient()

    def dummy_client(_url: str) -> mongomock.MongoClient[Comic]:
        print("Called!")
        return client

    monkeypatch.setattr(check_feeds_and_update, "MongoClient", dummy_client)
    return client


@pytest.fixture()
def report_regular_checks(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    args: dict[str, object] = {}

    def report_args(
        comics: Collection[Comic],
        hash_seed: int,
        webhook_url: str,
        thread_webhook_url: str,
        timeout: ClientTimeout = DEFAULT_AIOHTTP_TIMEOUT,
    ) -> None:
        args["comics"] = comics
        args["hash_seed"] = hash_seed
        args["webhook_url"] = webhook_url
        args["thread_webhook_url"] = thread_webhook_url

    monkeypatch.setattr(
        "rss_to_webhook.check_feeds_and_update.regular_checks", report_args
    )
    return args


@pytest.fixture()
def report_daily_checks(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    args: dict[str, object] = {}

    def report_args(
        comics: Collection[Comic],
        webhook_url: str,
    ) -> None:
        args["comics"] = comics
        args["webhook_url"] = webhook_url

    monkeypatch.setattr(
        "rss_to_webhook.check_feeds_and_update.daily_checks", report_args
    )
    return args


@pytest.mark.usefixtures("_fake_env")
def test_runs_regular_checks(
    report_regular_checks: dict[str, object], fake_db: mongomock.MongoClient[Comic]
) -> None:
    print("step1")

    main([])
    assert report_regular_checks == {
        "hash_seed": HASH_SEED,
        "comics": fake_db[DB_NAME]["comics"],
        "thread_webhook_url": THREAD_WEBHOOK_URL,
        "webhook_url": WEBHOOK_URL,
    }


@pytest.mark.usefixtures("_fake_env")
def test_runs_test_checks(
    report_regular_checks: dict[str, object], fake_db: mongomock.MongoClient[Comic]
) -> None:
    print("step1")

    main(["--test"])
    assert report_regular_checks == {
        "hash_seed": HASH_SEED,
        "comics": fake_db[DB_NAME]["test-comics"],
        "thread_webhook_url": TEST_WEBHOOK_URL,
        "webhook_url": TEST_WEBHOOK_URL,
    }


@pytest.mark.usefixtures("_fake_env")
def test_runs_daily_checks(
    report_daily_checks: dict[str, object], fake_db: mongomock.MongoClient[Comic]
) -> None:
    print("step1")

    main(["--daily"])
    assert report_daily_checks == {
        "comics": fake_db[DB_NAME]["comics"],
        "webhook_url": DAILY_WEBHOOK_URL,
    }
