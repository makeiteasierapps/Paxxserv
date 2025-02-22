from datetime import datetime, timezone
import json
from bson import ObjectId
import logging
from pydantic import ValidationError, BaseModel
from typing import List, Optional, Dict, Any

from app.services.MongoDbClient import MongoDbClient

# Database Models
class Answer(BaseModel):
    question: str
    answer: str
    follow_up_question: Optional[str] = None

class InsightDocument(BaseModel):
    questions_data: Dict[str, Dict[str, List[Answer]]]
    messages: Optional[List[Dict[str, Any]]] = None
    analysis: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None

# OpenAI Function Response Models
class Category(BaseModel):
    name: str
    subcategory: str

class UserEntry(BaseModel):
    question: str
    answer: str
    category: Category
    follow_up_question: str

class FollowUpQuestion(BaseModel):
    question: str
    answer: Optional[str] = None
    category: Category

class OpenAIFunctionResponse(BaseModel):
    """
    Represents the structured response from OpenAI's function call for user insight extraction.
    
    This model matches the schema defined in the OpenAI function tool configuration and is used
    to parse and validate the AI's categorized interpretation of user responses.

    Attributes:
        user_entries (List[UserEntry]): A list of processed user responses, each containing
            the original question, answer, categorization, and follow-up questions.
    """
    user_entries: List[UserEntry]

class InsightService:
    def __init__(self, db, sio, uid):
        self.db = db
        self.sio = sio
        self.uid = uid
        
    async def get_user_insight(self) -> Optional[InsightDocument]:
        """
        Fetches the user's insight document.
        Returns None if no document is found.
        """
        insight_doc = await self.db['insight'].find_one({'uid': self.uid}, {'messages._id': 0, 'categories.all': 0, 'categories.all_subcategories': 0})
        if insight_doc:
            insight_doc['_id'] = str(insight_doc['_id'])
            return InsightDocument(**insight_doc)
        return None
        
    async def get_user_analysis(self) -> Optional[Dict[str, Any]]:
        insight_doc = await self.get_user_insight()
        if not insight_doc:
            return None
        return insight_doc.analysis
    
    async def create_message(self, message_from: str, message_content: str):
        """
        Creates a new message in the insight document.
        """
        current_time = datetime.now(timezone.utc).isoformat()
        new_message = {
            '_id': ObjectId(),
            'message_from': message_from,
            'content': message_content,
            'type': 'database',
            'current_time': current_time,
        }

        await self.db['insight'].update_one(
            {'uid': self.uid}, 
            {
                '$push': {'messages': new_message},
                '$set': {'updated_at': current_time}
            },
            upsert=True
        )

    async def update_profile_answer(self, answer_data: Dict[str, Any]):
        """
        Update or add an answer in the user's profile categories structure.
        The answer will be stored under its respective category and subcategory.
        """
        try:
            index = answer_data['index']
            updated_answer = answer_data['answer']
            category = answer_data['category']
            subcategory = answer_data['subcategory']
            category_path = f"questions_data.{category}.{subcategory}.{index}.answer"
            await self.db['insight'].update_one(
                {'uid': self.uid},
                {'$set': {category_path: updated_answer}}  # Set the answer at the specific index
            )

            return {'message': 'Answer updated successfully'}, 200
            
        except Exception as e:
            logging.error("Error updating profile answer: %s", e)
            raise
    
    def extract_user_data(self, user_entries: List[UserEntry]):
        # Return a dictionary indicating this is a background task
        # The actual processing will be handled by _handle_background_task
        # Process follow-up questions
        follow_up_questions = [
            FollowUpQuestion(question=entry['follow_up_question'], category=entry['category'])
            for entry in user_entries
        ]
        return {
            'background': 'Processing user data in the background. You will receive updates via socket.io events.',
            'function': self._process_user_data,
            'args': [user_entries],
            'follow_up_questions': follow_up_questions
        }
    
    def parse_function_call_arguments(self, arguments: List[UserEntry]) -> OpenAIFunctionResponse:
        """
        Parses and validates JSON arguments from the function call into an OpenAIFunctionResponse model.
        """
        try:
            return OpenAIFunctionResponse(user_entries=arguments)
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
                category = entry.category
                category_name = category.name.replace(' ', '_').lower()
                subcategory_name = category.subcategory.replace(' ', '_').lower()
                category_path = f"questions_data.{category_name}.{subcategory_name}"

                # Add category and subcategory if they don't exist
                await user_collection.update_one(
                    {'uid': self.uid},
                    {
                        '$addToSet': {
                            'categories.all': category_name,
                            'categories.all_subcategories': subcategory_name,
                            f'categories.{category_name}.subcategories': subcategory_name
                        }
                    },
                    upsert=True
                )

                # Convert the entry to a dict and remove the category field since it's handled separately
                entry_data = entry.model_dump()
                del entry_data['category']
                update_data['$push'][category_path] = entry_data

            # Perform update for the answers
            if update_data['$push']:
                await user_collection.update_one(update_query, update_data, upsert=True)

            # Emit updated data
            updated_data = await user_collection.find_one(
                {'uid': self.uid}, 
                {'_id': 0, 'questions_data': 1}
            )
            await self.sio.emit('insight_user_data', json.dumps(updated_data))

        except Exception as e:
            logging.error("Error processing user data: %s", str(e))