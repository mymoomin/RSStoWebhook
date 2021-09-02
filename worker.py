import os
from aiohttp.client_exceptions import ClientConnectorError
from dotenv import load_dotenv
from pymongo import MongoClient
import feedparser
import requests
from time import sleep
import asyncio
import aiohttp
import mmh3

from datetime import datetime
start = datetime.now()

load_dotenv()
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
HASH_SEED = int(os.environ.get("HASH_SEED"), 16)
MONGODB_URI = os.environ.get("MONGODB_URI")
comics = MongoClient(MONGODB_URI)['discord_rss']['comics']

timeout = aiohttp.ClientTimeout(sock_connect=5, sock_read=10)


def get_new_entries(comic, feed):
    if comic['hash'] == feed.hash:
        return ([], True)
    last_entries = comic['last_entries']
    i = 0
    num_entries = len(feed.entries)
    while(i < 20 and i < num_entries):
        if feed.entries[i].link in last_entries:
            return (feed.entries[i:0:-1], True)
        i += 1
    else:
        return ([feed.entries[0]], False)


def make_body(comic, entry):
    return {
        "username": comic['author']['name'],
        "avatar_url": comic['author']['url'],
        "content": f"<@&{comic['role_id']}>",
        "embeds": [
            {
                "color": comic['color'],
                "title": f"**{entry.get('title', comic['name'])}**",
                "url": entry.link,
                "description": f"New {comic['name']}!",
            },
        ],
    }


async def get_feed(
    session: aiohttp.ClientSession,
    comic,
    **kwargs
) -> dict:
    url = comic['url']
    print(f"Requesting {url}")
    try:
        resp = await session.request('GET', url=url, **kwargs)
        data = await resp.text()
        print(f"Received data for {comic['name']}")
        feed = feedparser.parse(data)
        setattr(feed, "hash", mmh3.hash_bytes(data, HASH_SEED))
        print(f"Parsed feed")
        return feed
    except Exception as e:
        print(f"Problem connecting to {comic['name']}")
        return e


async def get_feeds(comic_list, **kwargs):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for comic in comic_list:
            tasks.append(get_feed(session=session, comic=comic, **kwargs))
        feeds = await asyncio.gather(*tasks, return_exceptions=False)
        return feeds

comic_list = list(comics.find())
feeds = asyncio.get_event_loop().run_until_complete(get_feeds(comic_list, timeout=timeout))
print("done")
comics_and_feeds = zip(comic_list, feeds)

counter = 1
for comic, feed in comics_and_feeds:
    print(f"Checking {comic['name']}")
    if isinstance(feed, Exception):
        print(f"{type(feed).__name__}: {str(feed)}")
    else:
        entries, found = get_new_entries(comic, feed)
        if not found:
            print(f"Couldn't find last entry for {comic['name']}, defaulting to most recent entry")
        for entry in entries:
            sleep(0.4) if counter != 0 else sleep(50)
            body = make_body(comic, entry)
            r = requests.post(WEBHOOK_URL, None, body)
            print(f"{entry.get('title', entry.link)}: {r.status_code}: {r.reason}")
            h = r.headers
            print(f"{h['x-ratelimit-remaining']} of {h['x-ratelimit-limit']} requests left in the next {h['x-ratelimit-reset-after']} seconds")
            if r.status_code == 429:
                print(r.json())
                raise Exception("Ratelimit reached")
            counter = (counter + 1) % 30

        comics.update_one(
            {"name": comic['name']},
            {
                "$set": {"hash": feed.hash},
                "$push":
                    {"last_entries":
                        {"$each": [feed.entries[0].link], "$slice": -3}
                    }
            })

time_taken = (datetime.now() - start).seconds
print(f"All feeds checked in {time_taken//60} minutes and {time_taken % 60} seconds")
