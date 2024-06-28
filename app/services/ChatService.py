import os
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv

class ChatService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ChatService, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_name, mongo_uri=None):
        if not hasattr(self, 'is_initialized'):
            self.is_initialized = True
            self.mongo_uri = mongo_uri or self._load_mongo_uri()
            self.db_name = db_name
            self.client = None
            self.db = None

    def _load_mongo_uri(self):
        load_dotenv()
        return os.getenv('MONGO_URI')

    def _initialize_client(self):
        if self.client is None:
            try:
                self.client = MongoClient(self.mongo_uri)
                self.db = self.client[self.db_name]
            except Exception as e:
                print(f"Failed to connect to MongoDB: {e}")
                self.client = None
                self.db = None

    def create_chat_in_db(self, uid, chat_name, agent_model):
        self._initialize_client()
        if self.db is not None:
            new_chat = {
                'uid': uid,
                'chat_name': chat_name,
                'agent_model': agent_model,
                'created_at': datetime.utcnow()
            }
            result = self.db['chats'].insert_one(new_chat)
            return str(result.inserted_id)
        else:
            print("MongoDB connection is not initialized.")
            return None

    def get_all_chats(self, uid):
        self._initialize_client()
        if self.db is not None:
            # Query the conversations collection for conversations belonging to the user
            chats_cursor = self.db['chats'].find({'uid': uid}).sort('created_at', -1)
            
            # Function to recursively convert ObjectId to string
            def convert_objectid(obj):
                if isinstance(obj, ObjectId):
                    return str(obj)
                elif isinstance(obj, list):
                    return [convert_objectid(item) for item in obj]
                elif isinstance(obj, dict):
                    return {k: convert_objectid(v) for k, v in obj.items()}
                else:
                    return obj

            # Create a list of dictionaries with all fields, converting ObjectId to string
            chats = []
            for conv in chats_cursor:
                chat = convert_objectid(conv)
                chat['chatId'] = chat.pop('_id')  # Rename '_id' to 'chatId'
                chats.append(chat)
            return chats
        else:
            print("MongoDB connection is not initialized.")
            return []

    def get_single_chat(self, uid, chat_id):
        self._initialize_client()
        if self.db is not None:
            chat = self.db['chats'].find_one({'_id': ObjectId(chat_id), 'uid': uid})
            return chat if chat else None
        else:
            print("MongoDB connection is not initialized.")
            return None

    def delete_chat(self, chat_id):
        self._initialize_client()
        if self.db is not None:
            result = self.db['chats'].delete_one({'_id': ObjectId(chat_id)})
            return result.deleted_count
        else:
            print("MongoDB connection is not initialized.")
            return 0

    def create_message(self, chat_id, message_from, message_content):
        self._initialize_client()
        
        new_message = {
            '_id': ObjectId(),
            'message_from': message_from,
            'content': message_content,
            'type': 'database',
            'time_stamp': datetime.utcnow()
        }
        if self.db is not None:
            # Update the chat document to append the new message to the 'messages' array
            self.db.chats.update_one(
                {'_id': ObjectId(chat_id)}, 
                {'$push': {'messages': new_message}}
            )
        else:
            print("MongoDB connection is not initialized.")
        return new_message

    def delete_all_messages(self, chat_id):
        self._initialize_client()
        if self.db is not None:
            # Update the chat document to clear the 'messages' array
            self.db.chats.update_one(
                {'_id': ObjectId(chat_id)},
                {'$set': {'messages': []}}
            )
        else:
            print("MongoDB connection is not initialized.")
    
    def query_snapshots(self, pipeline):
        # need to pass in the collection name
        self._initialize_client()
        if self.db is not None:
            return list(self.db["chunks"].aggregate(pipeline))
        else:
            print("MongoDB connection is not initialized.")
            return []
    
    def close_connection(self):
        if self.client:
            self.client.close()

    def __enter__(self):
        self._initialize_client()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_connection()