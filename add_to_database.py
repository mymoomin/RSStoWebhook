import os
from dotenv import load_dotenv
from pymongo import MongoClient
import json
import feedparser
import requests
import mmh3

load_dotenv()
HASH_SEED = int(os.environ.get("HASH_SEED"), 16)
MONGODB_URI = os.environ.get("MONGODB_URI")
client = MongoClient(MONGODB_URI)
db = client["discord_rss"]
comics = db["comics"]


with open("comics.json", "r") as read_file:
    comic_list = json.load(read_file)

for comic in comic_list:
    result = comics.update_one({"name": comic["name"]}, {"$set": comic}, upsert=True)
    if result.upserted_id:
        print(f"{comic['name']} added")
    elif result.modified_count == 1:
        print(f"{comic['name']} updated")
    else:
        print(f"{comic['name']} left as-is")
    if comics.find_one({"name": comic["name"], "last_update": {"$exists": False}}):
        feed = feedparser.parse(comic["url"])
        if len(feed.entries) == 0:
            comics.delete_one({"name": comic["name"]})
            print(f"The rss feed for {comic['name']} is broken. It has been removed")
            print(comic['url'])
            continue
        else:
            comics.update_one({"name": comic["name"]}, {"$set": {"last_update": feed.entries[0].link}})
            print(f"Set last_update for {comic['name']}")
    if comics.find_one({"name": comic["name"], "hash": {"$exists": False}}):
        r = requests.get(comic['url'])
        hash = mmh3.hash_bytes(r.text, HASH_SEED)
        succesful = comics.update_one({"name": comic["name"]}, {"$set": {"hash": hash}}).acknowledged
        print(hash, succesful)

    
    