from openai import OpenAI
from dotenv import load_dotenv
import os

class OpenAiClient():
    def __init__(self, db=None, uid=None):
        self.db = db
        self.uid = uid
        self.client = self._get_client()

    def _get_client(self):
        api_key = self._get_user_api_key() if self.db is not None and self.uid else self._load_api_key()
        return OpenAI(api_key=api_key)

    def _get_user_api_key(self):
        user_doc = self.db['users'].find_one({'_id': self.uid}, {'open_key': 1})
        if not user_doc or 'open_key' not in user_doc:
            raise ValueError(f"No API key found for user with ID: {self.uid}")
        return user_doc['open_key']
    
    def _load_api_key(self):
        load_dotenv()
        return os.getenv('OPENAI_API_KEY')
    
    def embed_content(self, content, model="text-embedding-3-small"):
        response = self.client.embeddings.create(
            input=content,
            model=model,
        )
        return response.data[0].embedding
    
    def generate_chat_completion(self, messages, model="gpt-4", json=False, stream=False):
        kwargs = {"messages": messages, "model": model, "stream": stream}
        if json:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(**kwargs)
        return response if stream else response.choices[0].message.content
            
    def get_audio_speech(self, message, model="tts-1", voice="nova"):
        response = self.client.audio.speech.create(
            model=model,
            voice=voice,
            input=message,
        )
        return response