from datetime import datetime, timezone
import json
from bson import ObjectId
import logging
from pydantic import ValidationError, BaseModel
from typing import List
from app.services.MongoDbClient import MongoDbClient

class Category(BaseModel):
    name: str
    subcategory: str
    is_new_category: bool
    is_new_subcategory: bool

class UserEntry(BaseModel):
    question: str
    answer: str
    category: Category
    follow_up_question: str

class UserProfile(BaseModel):
    user_entries: List[UserEntry]

class InsightService:
    def __init__(self, db, sio, uid):
        self.db = db
        self.sio = sio
        self.uid = uid
        
    async def get_user_insight(self):
        """
        Fetches the user's insight document containing both question_set and user_profile.
        Returns None if no document is found.
        """
        insight_doc = await self.db['insight'].find_one({'uid': self.uid},{'messages._id': 0})
        insight_doc['_id'] = str(insight_doc['_id'])
        print(insight_doc)
        return insight_doc
        
    async def get_user_analysis(self):
        insight_doc = await self.get_user_insight()
        if not insight_doc:
            return None
        return insight_doc.get('analysis')
    
    async def load_questions(self):
        """
        Fetches the question/answers map from the user's profile.
        """
        insight_doc = await self.get_user_insight()
        if not insight_doc:
            return None
            
        return insight_doc.get('question_set')
    
    async def create_message(self, message_from, message_content):
        current_time = datetime.now(timezone.utc).isoformat()
        new_message = {
            '_id': ObjectId(),
            'message_from': message_from,
            'content': message_content,
            'type': 'database',
            'current_time': current_time,
        }

        # Update the chat document to append the new message and update the 'updated_at' field
        await self.db['insight'].update_one(
            {'uid': self.uid}, 
            {
                '$push': {'messages': new_message},
                '$set': {'updated_at': current_time}
            },
            upsert=True
        )

    async def update_profile_answer(self, question_id, answer):
        """
        Update a single answer in the user's profile for MongoDB.
        Assumes 'profile' is a separate collection with 'uid' as a reference.
        """
        await self.db['questions'].update_one(
            {'uid': self.uid, 'questions._id': question_id},
            {'$set': {'questions.$.answer': answer}}
        )

        return {'message': 'User answer updated'}, 200
    
    def extract_user_data(self, user_entries: List[UserEntry]):
        # Return a dictionary indicating this is a background task
        # The actual processing will be handled by _handle_background_task
        return {
            'background': 'Processing user data in the background. You will receive updates via socket.io events.',
            'function': self._process_user_data,
            'args': [user_entries]
        }
    
    def parse_function_call_arguments(self, arguments: List[UserEntry]) -> UserProfile:
        """
        Parses and validates JSON arguments from the function call into a UserProfile model.
        """
        try:
            user_profile = UserProfile(user_entries=arguments)
            return user_profile
        except json.JSONDecodeError as json_err:
            logging.error("Error decoding JSON: %s", json_err)
            raise
        except ValidationError as val_err:
            logging.error("Validation error: %s", val_err)
            raise

    async def _process_user_data(self, raw_arguments: str):
        try:
            # Parse function call arguments
            user_profile = self.parse_function_call_arguments(raw_arguments)
            
            # Get MongoDB connection
            db = MongoDbClient('paxxium').db
            user_collection = db['insight']
            
            update_query = {'uid': self.uid}  # Match user
            update_data = {'$push': {}}

            # Category-based update
            for entry in user_profile.user_entries:
                category = entry.category  # category is a single object, not a list
                category_path = f"categories.{category.name}.{category.subcategory}"
                # Convert the entry to a dict and remove the category field since it's handled separately
                entry_data = entry.model_dump()
                del entry_data['category']
                update_data['$push'].setdefault(category_path, []).append(entry_data)

            # Perform update
            await user_collection.update_one(update_query, update_data, upsert=True)

            # Emit updated data
            updated_profile = await user_collection.find_one(
                {'uid': self.uid}, 
                {'_id': 0, 'categories': 1}
            )
            print(updated_profile)
            await self.sio.emit('insight_user_data', json.dumps(updated_profile))

        except Exception as e:
            logging.error("Error processing user data: %s", str(e))
