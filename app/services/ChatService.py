from datetime import datetime
from bson import ObjectId
from .MongoDbClient import MongoDbClient

class ChatService:
    def __init__(self, db_name):
        self.db_client = MongoDbClient(db_name)
        self.db = self.db_client.connect()
        
    def create_chat_in_db(self, uid, chat_name, agent_model, system_prompt=None, chat_constants=None, use_profile_data=False):
        new_chat = {
            'uid': uid,
            'chat_name': chat_name,
            'agent_model': agent_model,
            'is_open': True,
            'created_at': datetime.utcnow()
        }
        # Add optional fields only if they are not None
        if system_prompt is not None:
            new_chat['system_prompt'] = system_prompt
        if chat_constants is not None:
            new_chat['chat_constants'] = chat_constants
        if use_profile_data is not None:
            new_chat['use_profile_data'] = use_profile_data

        result = self.db['chats'].insert_one(new_chat)
        return str(result.inserted_id)
        
    def get_all_chats(self, uid):
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

    def get_single_chat(self, uid, chat_id):
        chat = self.db['chats'].find_one({'_id': ObjectId(chat_id), 'uid': uid})
        return chat if chat else None

    def delete_chat(self, chat_id):
        result = self.db['chats'].delete_one({'_id': ObjectId(chat_id)})
        return result.deleted_count

    def update_settings(self, chat_id, chat_name, agent_model, system_prompt, chat_constants, use_profile_data):
        """
        Updates a chat in the database
        """
        update_result = self.db['chats'].update_one(
            {'_id': ObjectId(chat_id)},
            {'$set': {
                'chat_name': chat_name,
                'agent_model': agent_model,
                'system_prompt': system_prompt,
                'chat_constants': chat_constants,
                'use_profile_data': use_profile_data
                }}
        )
        return update_result

    def update_visibility(self, chat_id, is_open):
        """
        Updates the visibility of a chat in the database
        """

        self.db['chats'].update_one({'_id': ObjectId(chat_id)}, {'$set': {'is_open': is_open}})
        return True

    def create_message(self, chat_id, message_from, message_content):        
        new_message = {
            '_id': ObjectId(),
            'message_from': message_from,
            'content': message_content,
            'type': 'database',
            'time_stamp': datetime.utcnow()
        }

            # Update the chat document to append the new message to the 'messages' array
        self.db.chats.update_one(
            {'_id': ObjectId(chat_id)}, 
            {'$push': {'messages': new_message}}
        )

        return new_message

    def delete_all_messages(self, chat_id):
        # Update the chat document to clear the 'messages' array
        self.db.chats.update_one(
            {'_id': ObjectId(chat_id)},
            {'$set': {'messages': []}}
        )
    
    def query_snapshots(self, pipeline):
        # need to pass in the collection name
        return list(self.db["chunks"].aggregate(pipeline))

    def __del__(self):
        self.db_client.close()