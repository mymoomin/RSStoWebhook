import os
import sys
import time
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from pymongo import MongoClient

from rss_to_webhook.worker import main

if TYPE_CHECKING:
    from pymongo.collection import Collection


start = time.time()

load_dotenv()
WEBHOOK_URL = os.environ["TEST_WEBHOOK_URL"]
MONGODB_URI = os.environ["MONGODB_URI"]
HASH_SEED = int(os.environ["HASH_SEED"], 16)


class TestCollection:
    def __init__(self, collection_name: str = "test_comics"):
        self.collection: Collection = MongoClient(MONGODB_URI)["discord_rss"][
            collection_name
        ]

    def pop_last_update(self) -> int:
        result = self.collection.update_many(
            {},
            {
                "$pop": {
                    "last_entries": 1,
                },
            },
        )
        return result.modified_count

    def reset(self, field: str) -> int:
        result = self.collection.update_many(
            {field: {"$exists": True}},
            {
                "$set": {
                    field: "'hi!'",
                }
            },
        )
        return result.modified_count

    def reset_caching(self):
        modified_count = self.reset("hash")
        self.reset("last_modified")
        self.reset("etag")
        return modified_count

    def reset_last_modified(self):
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

    def end_to_end_test(self):
        self.reset_caching()
        self.pop_last_update()
        main(self.collection, HASH_SEED, WEBHOOK_URL)
        # Nothing more should be sent
        main(self.collection, HASH_SEED, WEBHOOK_URL)


if __name__ == "__main__":
    opts = [opt for opt in sys.argv[1:] if opt.startswith("-")]
    args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    comics = TestCollection("test_comics")
    if not args or "e2e" in args:
        comics.end_to_end_test()
        # No goal value so can't say if succeeded or failed
    if "make_body" in args:
        pass


# for comic in comics.find():
#     print(comic['name'])
#     feed = feedparser.parse(comic['url'])
#     oldest_entry = [feed.entries[min(len(feed.entries)-1, 5)].link] * 3
#     comics.update_one(
#         {"name": comic["name"]},
#         {"$set": {
#             "last_entries": oldest_entry,
#             "hash": b'\x0c\x83s\xa2}}w\xc2G\xff\x84\xec\x12J\xb3\xe5'
#         }})


# comic_list = list(comics.find())

# time_taken = (datetime.now() - start).seconds
# print(f"List of comics obtained in {time_taken//60} minutes "
# "and {time_taken % 60} seconds")

# async def get_feed(
#     session: aiohttp.ClientSession,
#     comic,
#     **kwargs
# ) -> dict:
#     url = comic['url']
#     print(f"Requesting {url}")
#     resp = await session.request('GET', url=url, **kwargs)
#     data = await resp.text()
#     print(f"Received data for {comic['name']}")
#     feed = feedparser.parse(data)
#     print(f"Parsed feed")
#     return feed


# async def get_feeds(comic_list, **kwargs):
#     async with aiohttp.ClientSession() as session:
#         tasks = []
#         for comic in comic_list:
#             tasks.append(get_feed(session=session, comic=comic, **kwargs))
#         feeds = await asyncio.gather(*tasks, return_exceptions=True)
#         return feeds


# if __name__ == '__main__':
#     feeds = asyncio.get_event_loop().run_until_complete(get_feeds(comic_list))

time_taken = int(time.time() - start)
print(f"Tests run in {time_taken//60} minutes and {time_taken % 60} seconds")
# print(f"{tagged} tagged feeds out of {total} feeds")
