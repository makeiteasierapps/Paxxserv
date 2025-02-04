from openai import OpenAI
from dotenv import load_dotenv
from app.utils.token_counter import token_counter
import os

class OpenAiClient:
    def __init__(self, db=None, uid=None):
        self.db = db
        self.uid = uid
        self.client = None

    async def initialize(self):
        """Initialize the OpenAI client asynchronously"""
        self.client = await self._get_client()

    async def _get_user_api_key(self):
        user_doc = await self.db['users'].find_one({'_id': self.uid}, {'open_key': 1})
        if not user_doc or 'open_key' not in user_doc:
            raise ValueError(f"No API key found for user with ID: {self.uid}")
        return user_doc['open_key']
    
    def _load_api_key(self):
        load_dotenv()
        return os.getenv('OPENAI_API_KEY')

    async def _get_client(self):
        api_key = await self._get_user_api_key() if self.db is not None and self.uid else self._load_api_key()
        return OpenAI(api_key=api_key)

    # Make all methods that use self.client async
    async def embed_content(self, content, model="text-embedding-3-small"):
        if not self.client:
            await self.initialize()
        response = self.client.embeddings.create(
            input=content,
            model=model,
        )
        return response.data[0].embedding
    
    async def generate_chat_completion(self, messages, model="gpt-4o-mini", json=False, stream=False):
        if not self.client:
            await self.initialize()
        kwargs = {"messages": messages, "model": model, "stream": stream}
        if json:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(**kwargs)
        return response if stream else response.choices[0].message.content
            
    async def get_audio_speech(self, message, model="tts-1", voice="nova"):
        if not self.client:
            await self.initialize()
        response = self.client.audio.speech.create(
            model=model,
            voice=voice,
            input=message,
        )
        return response
    
    async def generate_image(self, prompt, size, quality, style):
        if not self.client:
            await self.initialize()
        response = await self.client.images.generate(
            prompt=prompt, 
            size=size, 
            quality=quality, 
            style=style, 
            model='dall-e-3', 
            n=1,
        )
        return response.data[0].url
    
    async def summarize_content(self, content):
        if not self.client:
            await self.initialize()
        token_count = token_counter(content)
        if token_count > 10000:
            # Summarize each chunk individually
            return "Content is too long to summarize."
        response = await self.generate_chat_completion(
            model='gpt-4o-mini',
            messages=[
                {
                    'role': 'system', 
                    'content': 'You are a helpful assistant that summarizes the content of a document.'
                },
                {
                    'role': 'user',
                    'content': f'''
                    Please provide a detailed summary of the following document:
                    {content}
                    '''
                }
            ]
        )
        return response
    
    async def extract_structured_data(self, system_message, content, schema):
        if not self.client:
            await self.initialize()
        response = await self.client.chat.completions.parse(
            model='gpt-4o-mini',
            messages=[
                {
                    'role': 'system',
                    'content': system_message
                },
                {
                    'role': 'user',
                    'content': content
                }
            ],
            response_format=schema
        )
        return response.choices[0].message.parsed
