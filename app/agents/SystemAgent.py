import os
from pydantic import BaseModel, Field
from typing import List
from dspy import Signature, InputField, OutputField, LM, configure, TypedChainOfThought

from dotenv import load_dotenv
load_dotenv()

class CategoriesOutput(BaseModel):
    categories: List[str] = Field(description='A list of categories')

class SystemCategoryRoutingSignature(Signature):
    """
    From a user query and a list of categories, determine which category the user query should be routed to, if the category does not exist, return None. If query belongs to multiple categories, return all categories.
    """
    user_query = InputField()
    category_list = InputField()
    categories_output: CategoriesOutput = OutputField()

class SystemAgent:
    def __init__(self):
        self.openai_key = os.getenv('OPENAI_API_KEY')

        try:
            lm = LM('openai/gpt-4o')
            configure(lm=lm)
        except Exception as e:
            print(f"Failed to initialize dspy: {e}")

    def category_routing(self, user_query, category_list):
        category_routing = TypedChainOfThought(SystemCategoryRoutingSignature)
        result_pred = category_routing(user_query=user_query, category_list=category_list)
        return result_pred.categories_output.categories

