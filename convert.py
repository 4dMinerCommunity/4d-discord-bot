import pymongo
import json

database = pymongo.MongoClient()['4DBot']

with open('tags.json') as f:
    tags = json.load(f)


for k, v in tags.items():
    database.tags.insert_one({'name': k, 'text': v})

    