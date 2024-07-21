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
from bson import ObjectId

class TopicsOutput(BaseModel):
    topics: List[str]

class QuestionsOutput(BaseModel):
    questions: List[str]

class TopicItemsSignature(Signature):
    """
    Create a user anaylsis and a list of topics that will be of interes to the user based on the survey.
    """
    survey = InputField()
    user_analysis: str = OutputField()
    topics: TopicsOutput = OutputField(desc='A list of topics')

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
            analyses = []
            for category in answered_questions:
                category_id = ObjectId(category['_id'])
                category_name = category['category']
                questions = [f"Questions from the category: {category_name}"]
                for question_obj in category['questions']:
                    question = question_obj['question']
                    answer = question_obj['answer']
                    prompt = f'question: {question} \n answer: {answer}'
                    questions.append(prompt)
                questions_string = "\n".join(questions)
                analysis_prompt = TypedChainOfThought(TopicItemsSignature)
                response = analysis_prompt(survey=questions_string)
                analyses.append(f"{category_name} analysis: {response.user_analysis}")
                self.db['questions'].update_one(
                    {'_id': category_id}, 
                    {'$set': {'category_analysis': response.user_analysis}, '$addToSet': {'topics': {'$each': response.topics.topics}}},
                    
                )
                self.db['users'].update_one(
                    {'_id': self.uid}, 
                    {'$addToSet': {'topics': {'$each': response.topics.topics}}}  
                )
            combined_analysis = "\n\n".join(analyses)
            full_analysis_prompt = ChainOfThought('category_analyses -> full_analysis')
            response = full_analysis_prompt(category_analyses=combined_analysis)
            self.db['users'].update_one({'_id': self.uid}, {'$set': {'user_analysis': response.full_analysis}})
            return response.full_analysis
        except Exception as e:
            print(f"Error in generate_questions: {str(e)}")
            print(traceback.format_exc())
            return {'error': str(e)}
            
        
        return 'response'