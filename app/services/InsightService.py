from app.models.user_profile import UserProfile

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
        insight_cursor = self.db['insight'].find({'uid': self.uid})
        insight_array = []
        
        async for insight_doc in insight_cursor:
            insight_doc['_id'] = str(insight_doc['_id'])
            if fetch_answered:
                insight_doc['questions'] = [q for q in insight_doc['questions'] if q.get('answer') is not None]
                if not insight_doc['questions']:
                    continue
            insight_array.append(insight_doc)

        return insight_array
    
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
            with both foundational and objective information. Adhere to the schema provided, returning all fields and models even if empty."""

        user_profile = await self.llm_client.extract_structured_data(system_message, user_intro, UserProfile)
        print(user_profile)
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
        user_profile_json = str(user_profile_dict)
        question_set = await self.question_generator.generate_questions(user_profile_json)
        return user_profile_dict, question_set
    
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