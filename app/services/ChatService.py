from datetime import datetime
from bson import ObjectId

class ChatService:
    def __init__(self, db):
        self.db = db
        
    def create_chat_in_db(self, uid):
        new_chat = {
            'uid': uid,
            'chat_name': 'New Chat',
            'agent_model': 'gpt-4o-mini',
            'updated_at': datetime.utcnow()
        }

        self.db['chats'].insert_one(new_chat)
        return new_chat
        
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

    def update_settings(self, chat_id, **kwargs):
        """
        Updates a chat in the database with only the provided settings
        """
        update_fields = {k: v for k, v in kwargs.items() if v is not None}
        if update_fields:
            update_result = self.db['chats'].update_one(
                {'_id': ObjectId(chat_id)},
                {'$set': update_fields}
            )
            return update_result
        return None

    def create_message(self, chat_id, message_from, message_content):
        current_time = datetime.utcnow()
        new_message = {
            '_id': ObjectId(),
            'message_from': message_from,
            'content': message_content,
            'type': 'database',
            'current_time': current_time
        }

        # Update the chat document to append the new message and update the 'updated_at' field
        self.db.chats.update_one(
            {'_id': ObjectId(chat_id)}, 
            {
                '$push': {'messages': new_message},
                '$set': {'updated_at': current_time}
            }
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