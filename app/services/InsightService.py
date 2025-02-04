from app.models.user_profile import UserProfile
from pydantic import BaseModel

class InsightService:
    def __init__(self, db, uid, llm_client, question_generator):
        self.db = db
        self.uid = uid
        self.llm_client = llm_client
        self.question_generator = question_generator
        
        
    async def get_user_analysis(self):
        user_doc = await self.db['users'].find_one({'_id': self.uid}, {'analysis': 1})
        
        if user_doc:
            return user_doc.get('analysis')
        
        return None
    
    async def load_questions(self, fetch_answered=False):
        """
        Fetches the question/answers map from the user's profile in MongoDB.
        Assumes 'profile' is a separate collection with 'uid' as a reference.
        If fetchAnswered is True, only returns answered questions.
        """
        questions_cursor = self.db['questions'].find({'uid': self.uid})
        questions_array = []
        
        async for question_doc in questions_cursor:
            question_doc['_id'] = str(question_doc['_id'])
            if fetch_answered:
                question_doc['questions'] = [q for q in question_doc['questions'] if q.get('answer') is not None]
                if not question_doc['questions']:
                    continue
            questions_array.append(question_doc)

        return questions_array
    
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
    
    async def initial_user_onboarding(self, user_intro):
        system_message = """You are an expert at understanding and profiling users. 
            Based on the provided information, create a comprehensive user profile 
            with both foundational and objective information."""

        user_profile = self.llm_client.extract_structured_data(system_message, user_intro, UserProfile)
        unanswered_user_profile = self.get_unanswered_user_profile(user_profile)
        return unanswered_user_profile
    
    def has_content(self,value) -> bool:
        """Check if a value contains actual content."""
        if isinstance(value, (str, list)):
            return bool(value)  # Returns False for empty strings/lists
        return value is not None

    def get_unanswered_user_profile(self, user_profile: UserProfile) -> dict:
        """Create a structure containing only unanswered fields from the user profile."""
        def _filter_model(model: BaseModel) -> dict:
            return {
                field_name: (
                    _filter_model(field_value) if isinstance(field_value, BaseModel)
                    else [_filter_model(item) for item in field_value] if isinstance(field_value, list) and field_value and isinstance(field_value[0], BaseModel)
                    else field_value
                )
                for field_name, field_value in model
                if not self.has_content(field_value) or (
                    isinstance(field_value, BaseModel) and _filter_model(field_value)
                ) or (
                    isinstance(field_value, list) and field_value and 
                    isinstance(field_value[0], BaseModel) and 
                    any(_filter_model(item) for item in field_value)
                )
            }
        
        return _filter_model(user_profile)