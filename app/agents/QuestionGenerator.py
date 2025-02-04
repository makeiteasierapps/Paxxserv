import os
from openai import OpenAI
import traceback
from dspy import Signature, InputField, OutputField, ChainOfThought
from dspy.functional import TypedChainOfThought
from typing import List
from pydantic import BaseModel
import uuid
from app.models.user_profile import UserProfile

class QuestionGenerator():
    def __init__(self, db, uid, llm_client):
        self.db = db
        self.uid = uid
        self.llm_client = llm_client

    def generate_questions(self, content):
        try:
            pass
        except Exception as e:
            print(f"Error in generate_questions: {str(e)}")
            print(traceback.format_exc())
            yield {'error': str(e)}
            
        
        return ''