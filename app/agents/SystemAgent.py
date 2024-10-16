from dspy import Signature, InputField, OutputField, LM, configure, ChainOfThought
import os

from dotenv import load_dotenv
load_dotenv()

class SystemCategoryRoutingSignature(Signature):
    """
    From a user query and a list of categories, determine which category the user query should be routed to, if the category does not exist, return None.
    """
    user_query = InputField()
    category_list = InputField()
    category = OutputField(desc='A category from the list else None')

class SystemAgent:
    def __init__(self):
        self.openai_key = os.getenv('OPENAI_API_KEY')

        try:
            lm = LM('openai/gpt-4o')
            configure(lm=lm)
        except Exception as e:
            print(f"Failed to initialize dspy: {e}")

    def category_routing(self, user_query, category_list):
        category_routing = ChainOfThought(SystemCategoryRoutingSignature)
        result_pred = category_routing(user_query=user_query, category_list=category_list)
        return result_pred.category

