from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import logging

class MongoDbClient:
    def __init__(self, db_name):
        self.logger = logging.getLogger(__name__)
        self.mongo_uri = self._load_mongo_uri()
        self.db_name = db_name
        self._client = None
        self._db = None
        self._connect()

    def _load_mongo_uri(self):
        load_dotenv(override=True)
        uri = os.getenv('MONGO_URI_DEV') if os.getenv('LOCAL_DEV') == 'true' else os.getenv('MONGO_URI')
        self.logger.info("Loaded MongoDB URI: %s", uri)
        return uri

    def _connect(self):
        if not self._client:
            self.logger.info("Attempting to connect to MongoDB at %s", self.mongo_uri)
            try:
                self._client = AsyncIOMotorClient(self.mongo_uri)
                self._db = self._client[self.db_name]
                self.logger.info("Successfully connected to MongoDB database: %s", self.db_name)
            except Exception as e:
                self.logger.error("Failed to connect to MongoDB: %s", str(e))
                raise

    @property
    def db(self):
        if self._db is None:
            self._connect()
        return self._db

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
            self._db = None