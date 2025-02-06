from app.models.questions import QuestionSet
from app.models.user_profile import UserProfile

class QuestionGenerator:
    def __init__(self, llm_client):
        self.llm_client = llm_client 
    async def generate_questions(self, user_profile: UserProfile):
        try:
            system_message = """You are an expert at crafting insightful and personalized questions.
                Based on the missing information in the user profile, generate a set of foundational and objective questions.
                """ 
            # Directing the LLM to format its output according to the QuestionSet schema
            question_set = await self.llm_client.extract_structured_data(system_message, user_profile, QuestionSet) 
            return question_set
        except Exception as e:
            print(f"Error in generate_questions: {str(e)}")
            return {'error': str(e)}