from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Self

from dotenv import load_dotenv
from pymongo import MongoClient

from rss_to_webhook.worker import main

if TYPE_CHECKING:
    from pymongo.collection import Collection

    from rss_to_webhook.db_types import Comic


start = time.time()

load_dotenv()
WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
THREAD_WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
MONGODB_URI = os.environ["MONGODB_URI"]
HASH_SEED = int(os.environ["HASH_SEED"], 16)
client: MongoClient[Comic] = MongoClient(MONGODB_URI)


class TestCollection:
    def __init__(self: Self, collection_name: str = "test-comics") -> None:
        self.collection: Collection[Comic] = client["test-database"][collection_name]

    def pop_last_update(self: Self) -> int:
        result = self.collection.update_many(
            {},
            {
                "$pop": {
                    "last_entries": 1,
                },
            },
        )
        return result.modified_count

    def reset(self: Self, field: str) -> int:
        result = self.collection.update_many(
            {field: {"$exists": True}},
            {
                "$set": {
                    field: "'hi!'",
                }
            },
        )
        return result.modified_count

    def reset_caching(self: Self) -> int:
        modified_count = self.reset("feed_hash")
        self.reset("last_modified")
        self.reset("etag")
        return modified_count

    def reset_last_modified(self: Self) -> int:
        result = self.collection.update_many(
            {"last_modified": {"$exists": True}},
            {
                "$set": {
                    "last_modified": (
                        "Tho, 32 Undecember 20022 40:0.1:99 GiantMagellanTelescope"
                    ),
                }
            },
        )
        return result.modified_count

    def end_to_end_test(self: Self) -> None:
        self.reset_caching()
        self.pop_last_update()
        print("test starts")
        main(self.collection, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)
        # Nothing more should be sent
        main(self.collection, HASH_SEED, WEBHOOK_URL, THREAD_WEBHOOK_URL)


if __name__ == "__main__":
    print("start")
    comics = TestCollection("test-comics")
    print("clearing caches")
    comics.end_to_end_test()
    # No goal value so can't say if succeeded or failed

time_taken = int(time.time() - start)
print(f"Tests ran in {time_taken // 60} minutes and {time_taken % 60} seconds")
