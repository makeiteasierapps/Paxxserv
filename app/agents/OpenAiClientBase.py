from openai import OpenAI
from dotenv import load_dotenv
import os

class OpenAiClientBase:
    def __init__(self, db=None, uid=None):
        self.db = db
        self.uid = uid
        self.openai_client = self._get_openai_client()

    def _get_openai_client(self):
        if not self.db or not self.uid:
            api_key = self._load_openai_key()
        else:
            api_key = self._get_user_api_key()
        return OpenAI(api_key=api_key)

    def _get_user_api_key(self):
        user_doc = self.db['users'].find_one({'_id': self.uid}, {'open_key': 1})
        return user_doc['open_key']
    
    def _load_openai_key(self):
        load_dotenv()
        return os.getenv('OPENAI_API_KEY')
    
    def embed_content(self, content, model="text-embedding-3-small"):
        response = self.openai_client.embeddings.create(
            input=content,
            model=model,
        )
        return response.data[0].embedding
    
    def pass_to_openai(self, messages, model="gpt-4o", json=False):
        kwargs = {
            "messages": messages,
            "model": model,
        }
        if json:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.openai_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content if not json else response.choices[0].message.content
            
    