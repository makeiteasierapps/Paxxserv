from datetime import datetime, timezone
from bson import ObjectId

class ChatService:
    def __init__(self, db):
        self.db = db
        
    async def create_chat_in_db(self, uid):
        new_chat = {
            'uid': uid,
            'chat_name': 'New Chat',
            'agent_model': 'gpt-4o-mini',
            'system_message': '',
            'context': [],
            'updated_at': datetime.now(timezone.utc).isoformat()
        }

        result = await self.db['chats'].insert_one(new_chat)
        new_chat.pop('_id')
        new_chat['chatId'] = str(result.inserted_id)
        return new_chat
        
    async def get_all_chats(self, uid):
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

        # Get all chats and convert to list
        chats = []
        async for conv in chats_cursor:
            chat = convert_objectid(conv)
            chat['chatId'] = chat.pop('_id')  # Rename '_id' to 'chatId'
            chats.append(chat)
        return chats

    async def get_single_chat(self, uid, chat_id):
        chat = await self.db['chats'].find_one({'_id': ObjectId(chat_id), 'uid': uid})
        return chat if chat else None

    async def delete_chat(self, chat_id):
        result = await self.db['chats'].delete_one({'_id': ObjectId(chat_id)})
        return result.deleted_count

    async def update_settings(self, chat_id, **kwargs):
        """
        Updates a chat in the database with only the provided settings
        """
        update_fields = {k: v for k, v in kwargs.items() if v is not None}
        if update_fields:
            update_result = await self.db['chats'].update_one(
                {'_id': ObjectId(chat_id)},
                {'$set': update_fields}
            )
            return update_result
        return None

    async def create_message(self, chat_id, message_from, message_content,):
        current_time = datetime.now(timezone.utc).isoformat()
        new_message = {
            '_id': ObjectId(),
            'message_from': message_from,
            'content': message_content,
            'type': 'database',
            'current_time': current_time,
        }

        # Update the chat document to append the new message and update the 'updated_at' field
        await self.db.chats.update_one(
            {'_id': ObjectId(chat_id)}, 
            {
                '$push': {'messages': new_message},
                '$set': {'updated_at': current_time}
            }
        )

        return new_message

    async def delete_all_messages(self, chat_id):
        # Update the chat document to clear the 'messages' array
        await self.db.chats.update_one(
            {'_id': ObjectId(chat_id)},
            {'$set': {'messages': []}}
        )
