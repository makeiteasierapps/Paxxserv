import os
from typing import List
from dspy import Signature, InputField, OutputField, LM, configure, Predict

from dotenv import load_dotenv
load_dotenv()

class SystemCategoryRoutingSignature(Signature):
    """
    Direct the user to where they need to go.
    """
    user_query: str = InputField()
    users_file_categories: List[str] = InputField()
    suggested_categories_list: List[str] = OutputField()

class SystemFileRoutingSignature(Signature):
    """
    Direct the user to the file(s) they need.
    """
    user_query: str = InputField()
    users_file_paths: List[str] = InputField()
    suggested_file_paths_list: List[str] = OutputField()

class SystemAgent:
    def __init__(self):
        self.openai_key = os.getenv('OPENAI_API_KEY')

        try:
            lm = LM('openai/gpt-4o-mini')
            configure(lm=lm)
        except Exception as e:
            print(f"Failed to initialize dspy: {e}")

    def category_routing(self, user_query, category_list):
        print(category_list)
        category_routing = Predict(SystemCategoryRoutingSignature)
        result_pred = category_routing(user_query=user_query, users_file_categories=category_list)
        return result_pred.suggested_categories_list

    def file_routing(self, user_query, file_list):
        file_routing = Predict(SystemFileRoutingSignature)
        result_pred = file_routing(user_query=user_query, users_file_paths=file_list)
        return result_pred.suggested_file_paths_list

