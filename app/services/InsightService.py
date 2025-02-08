from app.models.user_profile import UserProfile
from app.agents.OpenAiClient import OpenAiClient
import asyncio
import json
import logging
class InsightService:
    def __init__(self, db, sio, uid, question_generator):
        self.db = db
        self.sio = sio
        self.uid = uid
        self.openai_client = OpenAiClient(db, uid)
        self.question_generator = question_generator
        
    async def get_user_insight(self):
        """
        Fetches the user's insight document containing both question_set and user_profile.
        Returns None if no document is found.
        """
        insight_doc = await self.db['insight'].find_one({'uid': self.uid})
        insight_doc['_id'] = str(insight_doc['_id'])
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
    
    def extract_user_data(self, user_info: str):
        # Return a dictionary indicating this is a background task
        # The actual processing will be handled by _handle_background_task
        return {
            'background': 'Processing user data in the background. You will receive updates via socket.io events.',
            'function': self._process_user_data,
            'args': [user_info]
        }
    
    async def _process_user_data(self, user_info: str):
        """Internal method to process user data asynchronously"""
        try:
            system_message = """You are an expert at understanding and profiling users. 
                Based on the provided information, create a comprehensive user profile 
                with both foundational and objective information. Adhere to the schema provided, returning all fields and models even if empty."""

            user_profile = await self.openai_client.extract_structured_data(system_message, user_info, UserProfile)
            
            # Convert the Pydantic model to JSON while preserving class names
            def model_to_dict(obj):
                if hasattr(obj, '__class__') and hasattr(obj, 'model_dump'):
                    class_name = obj.__class__.__name__
                    if class_name == "UserProfile":
                        return {
                            "foundational": [model_to_dict(item) for item in obj.foundational],
                            "objective": [model_to_dict(item) for item in obj.objective]
                        }
                    
                    # For all other Pydantic models
                    data = obj.model_dump()
                    data["category"] = class_name
                    return {k: model_to_dict(v) for k, v in data.items()}
                elif isinstance(obj, list):
                    return [model_to_dict(item) for item in obj]
                elif isinstance(obj, dict):
                    return {k: model_to_dict(v) for k, v in obj.items()}
                return obj
            
            user_profile_dict = model_to_dict(user_profile)
            user_profile_json = json.dumps(user_profile_dict)
            await self.sio.emit('insight_user_data', user_profile_json)
            
            question_set = await self.question_generator.generate_questions(user_profile_json)
            question_set_dict = model_to_dict(question_set)
            question_set_json = json.dumps(question_set_dict)
            await self.sio.emit('insight_question_data', question_set_json)
        except Exception as e:
            logging.error("Error processing user data in background task: %s", str(e))

    
    # def has_content(self,value) -> bool:
    #     """Check if a value contains actual content."""
    #     if isinstance(value, (str, list)):
    #         return bool(value)  # Returns False for empty strings/lists
    #     return value is not None

    # def get_unanswered_user_profile(self, user_profile: UserProfile) -> dict:
    #     """Create a structure containing only unanswered fields from the user profile."""
    #     def _filter_model(model: BaseModel) -> dict:
    #         return {
    #             field_name: (
    #                 _filter_model(field_value) if isinstance(field_value, BaseModel)
    #                 else [_filter_model(item) for item in field_value] if isinstance(field_value, list) and field_value and isinstance(field_value[0], BaseModel)
    #                 else field_value
    #             )
    #             for field_name, field_value in model
    #             if not self.has_content(field_value) or (
    #                 isinstance(field_value, BaseModel) and _filter_model(field_value)
    #             ) or (
    #                 isinstance(field_value, list) and field_value and 
    #                 isinstance(field_value[0], BaseModel) and 
    #                 any(_filter_model(item) for item in field_value)
    #             )
    #         }
        
    #     return _filter_model(user_profile)