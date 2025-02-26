import os
import traceback
from dspy import Signature, InputField, OutputField, ChainOfThought, LM, configure
from typing import List
from pydantic import BaseModel
from bson import ObjectId

class TopicsOutput(BaseModel):
    topics: List[str]

class TopicItemsSignature(Signature):
    """
    Create a user anaylsis and a list of topics that will be of interest to the user based on the survey.
    """
    survey = InputField()
    user_analysis: str = OutputField()
    topics: TopicsOutput = OutputField(desc='A list of topics')

class AnalyzeUser():
    def __init__(self, db, uid):
        self.db = db
        self.uid = uid
        self.openai_key = os.getenv('OPENAI_API_KEY')
        try:
            lm = LM('openai/gpt-4o-mini')
            configure(lm=lm)
        except Exception as e:
            print(f"Failed to initialize dspy: {e}")
    
    def analyze_category(self, answered_questions):
        try:
            analyses = []
            for category in answered_questions:
                category_id = ObjectId(category['_id'])
                category_name = category['category']
                questions_string = self._format_questions(category)
                
                analysis_prompt = ChainOfThought(TopicItemsSignature)
                response = analysis_prompt(survey=questions_string)
                
                analyses.append(f"{category_name} analysis: {response.user_analysis}")
                self._update_database(category_id, response)

            combined_analysis = "\n\n".join(analyses)
            full_analysis = self._generate_full_analysis(combined_analysis)
            return full_analysis
        except Exception as e:
            print(f"Error in analyze_category: {str(e)}")
            print(traceback.format_exc())
            return {'error': str(e)}

    def _format_questions(self, category):
        questions = [f"Questions from the category: {category['category']}"]
        questions.extend(f"question: {q['question']}\nanswer: {q['answer']}" for q in category['questions'])
        return "\n".join(questions)

    def _update_database(self, category_id, response):
        self.db['questions'].update_one(
            {'_id': category_id}, 
            {'$set': {'category_analysis': response.user_analysis}, 
             '$addToSet': {'topics': {'$each': response.topics.topics}}}
        )
        self.db['users'].update_one(
            {'_id': self.uid}, 
            {'$addToSet': {'topics': {'$each': response.topics.topics}}}
        )

    def _generate_full_analysis(self, combined_analysis):
        full_analysis_prompt = ChainOfThought('category_analyses -> full_analysis')
        response = full_analysis_prompt(category_analyses=combined_analysis)
        self.db['users'].update_one({'_id': self.uid}, {'$set': {'user_analysis': response.full_analysis}})
        return response.full_analysis
