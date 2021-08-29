import json

with open("comics.json", "r") as read_file:
    comic_list = json.load(read_file)

for comic in comic_list:
    print(comic['name'])