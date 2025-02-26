import dspy
from dotenv import load_dotenv
import os
from dspy import Signature, InputField, OutputField, LM, configure, Predict
from pydantic import BaseModel
from typing import List, Dict

load_dotenv()
# OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
class Result(BaseModel):
    belongs: bool
    category: str


class GenerateNewCategorySignature(Signature):
    """
    Generate a new category based on the file path for an Ubuntu server.
    """
    file_path = InputField()
    new_category = OutputField()

class DoesFileBelongInCategorySignature(Signature):
    """
    Determine if a file belongs in a category.
    """
    file_path = InputField()
    category_list = InputField()
    result: Result = OutputField(desc='A Result object containing a dictionary with "belongs" (bool) and "category" (str) fields. If the file belongs in a category, "belongs" should be True and "category" should be the matching category. Otherwise, "belongs" should be False and "category" should be an empty string.')

class CategoryAgent:
    def __init__(self):
        self.model = 'gpt-4o'
        self.openai_key = os.getenv('OPENAI_API_KEY')

        try:
            lm = LM('openai/gpt-4o-mini')
            configure(lm=lm)
        except Exception as e:
            print(f"Failed to initialize dspy: {e}")
        
    def does_file_belong_in_category(self, file_path, category_list):
        try:
            # Convert category_list to a string representation
            category_list_str = ', '.join(category_list)
            does_file_belong_in_category = Predict(DoesFileBelongInCategorySignature)
            result_pred = does_file_belong_in_category(file_path=file_path, category_list=category_list_str)
            result_obj = {
                "belongs": result_pred.result.belongs,
                "category": result_pred.result.category
            }
            print(result_obj)
            return result_obj
        except Exception as e:
            print(f"An error occurred: {e}")
            return Result(belongs=False, category="")
        
    def create_new_category(self, file_path):
        try:
            generate_new_category = Predict(GenerateNewCategorySignature)
            result_pred = generate_new_category(file_path=file_path)
            print(result_pred.new_category)
            return result_pred.new_category
        except Exception as e:
            print(f"An error occurred: {e}")
            return ""