import json
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
MONGODB_URI = os.environ.get("MONGODB_URI")
comics = MongoClient(MONGODB_URI)['discord_rss']['comics']

with open("comics.json", "r") as read_file:
    json_comics = json.load(read_file)
    json_names = set([comic['name'] for comic in json_comics])

db_comics = comics.find()
db_names = set([comic['name'] for comic in db_comics])

print("In both lists:")
for name in db_names & json_names:
    print("\t", name)
    
print("Only in comics.json:")
for name in json_names - db_names:
    print("\t", name)
    
print("Only in database:")
for name in db_names - json_names:
    print("\t", name)