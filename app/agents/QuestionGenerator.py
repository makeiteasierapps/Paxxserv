import os
import dspy
import traceback
from dspy import Signature, InputField, OutputField, ChainOfThought
from dspy.functional import TypedChainOfThought
from .OpenAiClientBase import OpenAiClientBase
from typing import List
from pydantic import BaseModel

class QuestionsOutput(BaseModel):
    questions: List[str]

category_details = [
    'Personal Background: Questions focusing on their age, family, upbringing, and significant life events. Understanding their background can provide insights into their current life situation and values.'
]

class QuestionGeneratorSignature(Signature):
    """
    Create a list of questions based on the user's details and category.
    """
    user_details = InputField()
    category = InputField()
    questions: QuestionsOutput = OutputField(desc='The questions should be personalized based on the users details contained within a list')

class QuestionGenerator(OpenAiClientBase):
    def __init__(self, db, uid):
        super().__init__(db, uid)
        self.openai_key = os.getenv('OPENAI_API_KEY')
        try:
            lm = dspy.OpenAI(model='gpt-3.5-turbo', max_tokens=1000, api_key=self.openai_key)
            dspy.settings.configure(lm=lm)
        except Exception as e:
            print(f"Failed to initialize dspy: {e}")
    
    def generate_questions(self, content):
        try:
            user_details = ChainOfThought('user_introduction -> extracted_details')
            response = user_details(user_introduction=content)
            question_generator = TypedChainOfThought(QuestionGeneratorSignature)
            for category in category_details:
                try:
                    questions_response = question_generator(user_details=response.extracted_details, category=category)
                    questions_list = questions_response.questions.questions
                    yield {
                        'category': category,
                        'questions': questions_list,
                    }
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
            with open('dspyOutputLogs.txt', 'a', encoding='utf-8') as file:
                file.write(f'Response: {questions_response.questions}\n')
                file.write(f'Rationale: {questions_response.rationale}\n')
        
        return response