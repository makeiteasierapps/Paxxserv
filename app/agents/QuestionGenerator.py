import os
import dspy
import traceback
from dspy import Signature, InputField, OutputField, ChainOfThought
from dspy.functional import TypedChainOfThought
from typing import List
from pydantic import BaseModel
import uuid

class QuestionsOutput(BaseModel):
    questions: List[str]

category_details = [
    'Personal Background: Questions focusing on their age, family, upbringing, and significant life events. Understanding their background can provide insights into their current life situation and values.',
    'Education and Career: Inquire about their educational history, current job, career goals, and aspirations. This information can help you provide career-related advice and understand their professional challenges.',
    'Physical and Mental Health: Include questions about their general health, wellness habits, mental health state, and any persistent issues or disabilities. This is crucial for recommending lifestyle adjustments or ways to seek appropriate support.',
    'Interests and Hobbies: Learning about what they enjoy doing in their free time, their passions, and hobbies. This can help in suggesting activities that could improve their quality of life or relieve stress.',
    'Current Life Situation: Questions about their current living situation, day-to-day responsibilities, and any immediate concerns or stressors they are facing. This helps in understanding what assistance or advice is most relevant to their current needs.',
    'Social Relationships: Inquiring about their relationship with family, friends, and significant others. A person\'s social supports and challenges play a large role in their overall well-being.',
    'Goals and Aspirations: Understanding their short-term and long-term goals, dreams, and what they desire most in their personal and professional lives. This helps in providing guidance that is aligned with their objectives.'
]

class QuestionGeneratorSignature(Signature):
    """
    Create a list of questions based on the user's details and category.
    """
    user_details = InputField()
    category = InputField()
    questions: QuestionsOutput = OutputField(desc='The questions should be personalized based on the users details contained within a list')

class QuestionGenerator():
    def __init__(self, db, uid):
        self.db = db
        self.uid = uid
        self.openai_key = os.getenv('OPENAI_API_KEY')
        try:
            lm = dspy.OpenAI(model='gpt-4o-mini', max_tokens=1000, api_key=self.openai_key)
            dspy.settings.configure(lm=lm)
        except Exception as e:
            print(f"Failed to initialize dspy: {e}")
    
    def generate_questions(self, content):
        try:
            user_details = ChainOfThought('user_introduction -> extracted_details')
            response = user_details(user_introduction=content)
            question_generator = TypedChainOfThought(QuestionGeneratorSignature)
            questions = []
            for category in category_details:
                try:
                    questions_response = question_generator(user_details=response.extracted_details, category=category)
                    questions_list = questions_response.questions.questions
                    questions_object = {
                        'uid': self.uid,
                        'category': category.split(':', 1)[0].strip(),
                        'questions': [{'_id': str(uuid.uuid4()), 'question': q, 'answer': None} for q in questions_list]
                    }
                    yield questions_object
                    
                    questions.append(questions_object)
                    questions_object.pop('_id', None)
                    self.db['questions'].insert_one(questions_object)
                
                except Exception as e:
                    print(f"Error generating questions for category {category}: {str(e)}")
                    print(traceback.format_exc())
                    yield {
                        'category': category,
                        'error': str(e)
                    }
        except Exception as e:
            print(f"Error in generate_questions: {str(e)}")
            print(traceback.format_exc())
            yield {'error': str(e)}
            
        
        return response