import os
from dotenv import load_dotenv
from pymongo import MongoClient
import feedparser
import asyncio
import aiohttp
import mmh3
import requests

from datetime import datetime
start = datetime.now()

load_dotenv()
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
MONGODB_URI = os.environ.get("MONGODB_URI")
HASH_SEED = int(os.environ.get("HASH_SEED"), 16)
comics = MongoClient(MONGODB_URI)["discord_rss"]["comics"]

for comic in comics.find():
    print(comic['name'])
    rss = feedparser.parse(comic['url'])
    oldest_entry = rss.entries[min(len(rss.entries)-1, 1)].link
    comics.update_one({"name": comic["name"]}, {"$set": {"last_update": oldest_entry, "hash": b'\x0c\x83s\xa2}}w\xc2G\xff\x84\xec\x12J\xb3\xe5'}})

# total, tagged = 0, 0

# comic_list = list(comics.find())

# time_taken = (datetime.now() - start).seconds
# print(f"List of comics obtained in {time_taken//60} minutes and {time_taken % 60} seconds")

# for comic in comic_list:
#     rss = feedparser.parse(comic['url'])
#     etag = 'etag' in rss
#     modified = 'modified' in rss
#     print(f"{comic['name']}: {etag=}, {modified=}")
#     total += 1
#     if etag or modified:
#         tagged += 1

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

time_taken = (datetime.now() - start).seconds
print(f"All feeds checked in {time_taken//60} minutes and {time_taken % 60} seconds")
# print(f"{tagged} tagged feeds out of {total} feeds")