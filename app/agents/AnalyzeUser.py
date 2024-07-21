import os
import json
import dspy
import traceback
from dspy import Signature, InputField, OutputField, ChainOfThought
from dspy.functional import TypedChainOfThought
from .OpenAiClientBase import OpenAiClientBase
from typing import List
from pydantic import BaseModel
import uuid

class QuestionsOutput(BaseModel):
    questions: List[str]

class QuestionGeneratorSignature(Signature):
    """
    Create a list of questions based on the user's details and category.
    """
    user_details = InputField()
    category = InputField()
    questions: QuestionsOutput = OutputField(desc='The questions should be personalized based on the users details contained within a list')

class AnalyzeUser(OpenAiClientBase):
    def __init__(self, db, uid):
        super().__init__(db, uid)
        self.openai_key = os.getenv('OPENAI_API_KEY')
        try:
            lm = dspy.OpenAI(model='gpt-4o-mini', max_tokens=1000, api_key=self.openai_key)
            dspy.settings.configure(lm=lm)
        except Exception as e:
            print(f"Failed to initialize dspy: {e}")
    
    def analyze_cateogry(self, answered_questions):
        try:
            for category in answered_questions:
                for question_obj in category['questions']:
                    question = question_obj['question']
                    answer = question_obj['answer']
                    print(question)
                    print(answer)
                
        except Exception as e:
            print(f"Error in generate_questions: {str(e)}")
            print(traceback.format_exc())
            return {'error': str(e)}
            
        
        return 'response'