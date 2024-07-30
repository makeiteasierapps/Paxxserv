from openai import OpenAI
from dotenv import load_dotenv
import os

class OpenAiClientBase:
    def __init__(self, db=None, uid=None):
        self.db = db
        self.uid = uid
        self.openai_client = self._get_openai_client()

    def _get_openai_client(self):
        if self.db is None or self.uid is None:
            api_key = self._load_openai_key()
        else:
            api_key = self._get_user_api_key()
        return OpenAI(api_key=api_key)

    def _get_user_api_key(self):
        user_doc = self.db['users'].find_one({'_id': self.uid}, {'open_key': 1})
        if not user_doc or 'open_key' not in user_doc:
            raise ValueError(f"No API key found for user with ID: {self.uid}")
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
    
    def pass_to_openai(self, messages, model="gpt-4o", json=False, stream=False):
        kwargs = {
            "messages": messages,
            "model": model,
            "stream": stream,
        }
        if json:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.openai_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content if not stream else response
            
    def get_audio_speech(self, message, model="tts-1", voice="nova"):
        response = self.openai_client.audio.speech.create(
            model=model,
            voice=voice,
            input=message,
        )
        return response