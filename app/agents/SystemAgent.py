import os
from typing import List
from dspy import Signature, InputField, OutputField, LM, configure, Predict

from dotenv import load_dotenv
load_dotenv()

class SystemCategoryRoutingSignature(Signature):
    """
    From a user query and a list of categories, return a list of categories relevant to the user query.
    """
    user_query: str = InputField()
    category_list: List[str] = InputField()
    categories_list: List[str] = OutputField()

class SystemFileRoutingSignature(Signature):
    """
    From a user query and a list of files, return a list of files relevant to the user query.
    """
    user_query: str = InputField()
    file_list: List[str] = InputField()
    files_list: List[str] = OutputField()

class SystemAgent:
    def __init__(self):
        self.openai_key = os.getenv('OPENAI_API_KEY')

        try:
            lm = LM('openai/gpt-4o')
            configure(lm=lm)
        except Exception as e:
            print(f"Failed to initialize dspy: {e}")

    def category_routing(self, user_query, category_list):
        category_routing = Predict(SystemCategoryRoutingSignature)
        result_pred = category_routing(user_query=user_query, category_list=category_list)
        return result_pred.categories_list

    def file_routing(self, user_query, file_list):
        file_routing = Predict(SystemFileRoutingSignature)
        result_pred = file_routing(user_query=user_query, file_list=file_list)
        return result_pred.files_list

