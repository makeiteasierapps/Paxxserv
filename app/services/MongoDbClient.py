from pymongo import MongoClient
from dotenv import load_dotenv
import os

class MongoDbClient:
    def __init__(self, db_name):
        self.mongo_uri = self._load_mongo_uri()
        self.db_name = db_name
        self.client = None
        self.db = None

    def _load_mongo_uri(self):
        load_dotenv()
        return os.getenv('MONGO_URI')

    def connect(self):
        if not self.client:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
        return self.db

    def close(self):
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()