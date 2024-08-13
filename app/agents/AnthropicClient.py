import anthropic
from dotenv import load_dotenv
import os

class AnthropicClient():
    def __init__(self, db=None, uid=None):
        self.db = db
        self.uid = uid
        self.client = self._get_client()

    def _get_client(self):
        if self.db is None or self.uid is None:
            api_key = self._load_anthropic_key()
        else:
            api_key = self._get_user_api_key()
        return anthropic.Anthropic(api_key=api_key)

    def _get_user_api_key(self):
        user_doc = self.db['users'].find_one({'_id': self.uid}, {'anthropic_key': 1})
        if not user_doc or 'anthropic_key' not in user_doc:
            raise ValueError(f"No API key found for user with ID: {self.uid}")
        return user_doc['anthropic_key']
    
    def _load_anthropic_key(self):
        load_dotenv()
        return os.getenv('ANTHROPIC_API_KEY')
    
    def generate_chat_completion(self, messages, model, json=False, stream=False, system=None):
        print(model)
        kwargs = {"messages": messages, "model": model, "stream": stream, "max_tokens": 1000}
        if system:
            kwargs["system"] = system
        response = self.client.messages.create(**kwargs)
        return response if stream else response.content[0].text
