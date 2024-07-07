import os
import tiktoken
from openai import OpenAI
import dspy
from dspy import Signature, InputField, OutputField
from dspy.functional import TypedPredictor
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv
from flask_socketio import emit

class ActionItemsOutput(BaseModel):
    actions: List[str]

class ActionItemsSignature(Signature):
    """
    From the content, extract the suggested action items.
    """
    content = InputField()
    actions: ActionItemsOutput = OutputField(desc='Suggested actions should come directly from the content. If no actions are required, the output should be an empty list.')

class NewActionItemsSignature(Signature):
    """
    Create a new list of action items by combining two lists.
    """

    list_1 = InputField()
    list_2 = InputField()
    combined_list: ActionItemsOutput = OutputField()

class DocumentContent(Signature):
    """From the content, extract the title and summary of the document.
    """

    document = InputField()
    title = OutputField(desc='Short descriptive title of the document')
    summary = OutputField()
    
class BossAgent:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BossAgent, cls).__new__(cls)
        return cls._instance

    def __init__(self, openai_key=None, model='gpt-3.5-turbo', system_prompt="You are a friendly but genuine AI Agent. Don't be annoyingly nice, but don't be rude either.", chat_constants=None, user_analysis=None):
        if not hasattr(self, 'is_initialized'):
            self.is_initialized = True
            self.openai_key = openai_key or self._load_openai_key()
            self.model = model if model == 'gpt-4-turbo' else 'gpt-3.5-turbo'
            self.lm = None
            self.client = dspy.OpenAI(api_key=self.openai_key)  
            self.openai_client = OpenAI(api_key=self.openai_key)
            self.system_prompt = system_prompt
            self.chat_constants = chat_constants
            self.user_analysis = user_analysis

    def _load_openai_key(self):
        load_dotenv()
        return os.getenv('OPENAI_API_KEY')

    def _initialize_dspy(self):
        try:
            self.lm = dspy.OpenAI(model=self.model, api_key=self.openai_key)
            dspy.settings.configure(lm=self.lm)
        except Exception as e:
            print(f"Failed to initialize dspy: {e}")
            self.lm = None

    def extract_content(self, moment):
        self._initialize_dspy()
        content = moment['transcript']
        if self.lm:
            extract_actions = TypedPredictor(ActionItemsSignature)
            actions_pred = extract_actions(content=content)
            generate_summary_prompt = dspy.ChainOfThought(DocumentContent)
            content_pred = generate_summary_prompt(document=content)

            extracted_content = {
                'title': content_pred.title,
                'summary': content_pred.summary,
                'actionItems': actions_pred.actions.actions
            }
            return extracted_content
        else:
            print("dspy is not initialized.")
            return None
   
    def diff_snapshots(self, previous_snapshot, current_snapshot):
        self._initialize_dspy()
    
        # Takes the summary of the previous snapshot, combines it with the summary of the current snapshot, and generates a new summary.
        generate_new_summary_prompt = dspy.ChainOfThought('summary_1, summary_2 -> new_summary')
        new_summary_pred = generate_new_summary_prompt(summary_1=previous_snapshot['summary'], summary_2=current_snapshot['summary'])
        new_summary = new_summary_pred.new_summary

        # Takes the action items of the previous snapshot, combines it with the action items of the current snapshot, and generates a new list of action items.
        list_1_str = ', '.join(previous_snapshot['actionItems'])
        list_2_str = ', '.join(current_snapshot['actionItems'])
        generate_new_actions_prompt = TypedPredictor(NewActionItemsSignature)
        new_action_items_pred = generate_new_actions_prompt(list_1=list_1_str, list_2=list_2_str)
        new_action_items = new_action_items_pred.combined_list.actions

        # Takes the title of the previous snapshot, combines it with the title of the current snapshot, and generates a new title.
        generate_new_title_prompt = dspy.ChainOfThought('title_1, title_2 -> new_title')
        new_title_pred = generate_new_title_prompt(title_1=previous_snapshot['title'], title_2=current_snapshot['title'])
        new_title = new_title_pred.new_title

        new_snapshot = {
            'title': new_title,
            'summary': new_summary,
            'actionItems': new_action_items
        }
        return new_snapshot

    def embed_content(self, content):
        response = self.openai_client.embeddings.create(
            input=content,
            model="text-embedding-3-small",
        )
        return response.data[0].embedding
    
    def pass_to_boss_agent(self, chat_id, new_chat_history, save_callback=None):
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=new_chat_history,
            stream=True,
        )
        response_chunks = []
        inside_code_block = False
        language = None
        ignore_next_token = False

        for chunk in response:
            response_chunk = chunk.choices[0].delta.content
            if response_chunk is not None:
                response_chunks, inside_code_block, language, ignore_next_token = self.process_response_chunk(
                    chat_id, response_chunk, response_chunks, inside_code_block, language, ignore_next_token
                )

        collapsed_response = []
        if response_chunks:
            current_message = response_chunks[0]
            for chunk in response_chunks[1:]:
                if chunk['type'] == current_message['type']:
                    current_message['content'] += chunk['content']
                else:
                    collapsed_response.append(current_message)
                    current_message = chunk
            collapsed_response.append(current_message)

        # Notify the client that the stream is over
        end_stream_obj = {
            'message_from': 'agent',
            'content': response_chunks,
            'type': 'end_of_stream',
            'room': chat_id
        }
        emit('chat_response', end_stream_obj, room=chat_id)
        if save_callback:
            save_callback(chat_id, collapsed_response)

    def process_response_chunk(self, chat_id, response_chunk, response_chunks, inside_code_block, language, ignore_next_token):
        if ignore_next_token:
            ignore_next_token = False
            language = None
            return response_chunks, inside_code_block, language, ignore_next_token

        if response_chunk == '```':
            inside_code_block = not inside_code_block
            language = None if not inside_code_block else language
        elif response_chunk == '``':
            inside_code_block = not inside_code_block
            ignore_next_token = True
        else:
            if inside_code_block and language is None:
                language = response_chunk.strip()
            else:
                formatted_message = self.format_stream_message(response_chunk, inside_code_block, language)
                formatted_message['room'] = chat_id
                response_chunks.append(formatted_message)
                emit('chat_response', formatted_message, room=chat_id)
        
        return response_chunks, inside_code_block, language, ignore_next_token
    
    def format_stream_message(self, message, inside_code_block, language):
        if inside_code_block:
            return {
                'type': 'code',
                'content': message,
                'language': language or 'markdown',
            }
        else:
            return {
                'type': 'text',
                'content': message,
            }

    def process_message(self, chat_history, chat_id, user_message, system_message=None, save_callback=None, image_url=None):
        new_chat_history = self.manage_chat(chat_history, user_message, image_url)
        if system_message:
            new_chat_history.insert(0, system_message)
        
        if image_url:
            self.pass_to_vision_model(new_chat_history, chat_id, save_callback)
        else:
            self.pass_to_boss_agent(chat_id, new_chat_history, save_callback)
    
    def get_full_response(self, message):
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": message,
            }],
        )
        return response.choices[0].message.content
    
    def stream_audio_response(self, message):
        file_path = 'app/audioFiles/audio.mp3'
        
        # Delete the existing file if it exists
        if os.path.exists(file_path):
            os.remove(file_path)
        
        response = self.openai_client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=message,
        )

        response.stream_to_file(file_path)

        # for chunk in response.iter_bytes(chunk_size=4096):
        #     if chunk:
        #         yield chunk
 
    def manage_chat(self, chat_history, new_user_message, image_url=None):
        """
        Takes a chat object extracts x amount of tokens and returns a message
        object ready to pass into OpenAI chat completion
        """
        
        formatted_messages = [{
                "role": "system",
                "content": 
                f'''
                    {self.system_prompt}\n***USER ANALYSIS***\n{self.user_analysis}\n**************
                    ***THINGS TO REMEMBER***\n{self.chat_constants}\n**************
                ''',
            },
        ]
        token_limit = 2000
        token_count = 0
        for message in chat_history:
            print(message)
            if token_count > token_limit:
                break
            if message['message_from'] == 'user':
                token_count += self.token_counter(message['content'])
                formatted_messages.append({
                    "role": "user",
                    "content": message['content'],
                })
            else:
                token_count += self.token_counter(message['content'][0]['content'])
                formatted_messages.append({
                    "role": "assistant",
                    "content": message['content'][0]['content'],
                })

        if image_url:
            formatted_messages.append({
                "role": "user",
                "content": 
                [
                    {
                        "type": "text", 
                        "text": new_user_message
                    },
                    {
                        "type": "image_url",
                        "image_url": image_url
                    },
                ],
            })
        else:
            formatted_messages.append({
                "role": "user",
            "content": new_user_message,
        })
        
        return formatted_messages
    
    def prepare_vector_response(self, query_results, system_prompt=None):
        text = []

        for item in query_results:
            if item['score'] > 0.2:
                if 'transcript' in item:
                    text.append(item['transcript'])
                if 'actionItems' in item:
                    action_items = ', '.join(item['actionItems'])
                    text.append(action_items)
                if 'text' in item:
                    text.append(item['text'])
        combined_text = ' '.join(text)
        query_instructions = f'''
        \nAnswer the users question based off of the knowledge base provided below, provide 
        a detailed response that is relevant to the users question.\n
        KNOWLEDGE BASE: {combined_text}
        '''
        if system_prompt:
            query_instructions += f"\n{system_prompt}"
        
        system_message = {
            'role': 'system',
            'content': query_instructions
        }
        return system_message
    
    def create_vector_pipeline(self, query, project_id):
        embeddings = self.embed_content(query)
        pipeline = [
            {
                '$vectorSearch': {
                    'index': 'personal-kb',
                    'path': 'values',
                    'queryVector': embeddings,
                    'numCandidates': 100,
                    'limit': 5,
                    'filter': {
                        'project_id': project_id
                    }
                }
            }, {
                '$project': {
                    '_id': 0,
                    'text': 1,
                    'score': {
                        '$meta': 'vectorSearchScore'
                    }
                }
            }
        ]
    
        return pipeline
    
    def token_counter(self, message):
        """Return the number of tokens in a string."""
        try:
            encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            print("Warning: model not found. Using cl100k_base encoding.")
            encoding = tiktoken.get_encoding("cl100k_base")
        
        tokens_per_message = 3
        num_tokens = 0
        num_tokens += tokens_per_message
        num_tokens += len(encoding.encode(message))
        num_tokens += 3  # every reply is primed with <|im_start|>assistant<|im_sep|>
        return num_tokens
    
    def generate_image(self, request):
        prompt = request['prompt']
        size=request['size'].lower()
        quality=request['quality'].lower()
        style=request['style'].lower()
        

        response = self.openai_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size=size,
            quality=quality,
            style=style,
        )

        return response.data[0].url
    
    # This is just a normal call to chat completion without streaming the response
    # I think I should create a function that can handle both scenarios
    def pass_to_news_agent(self, article_to_summarize):
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": article_to_summarize,
                }
            ],
        )

        return response.choices[0].message.content
    
    def pass_to_profile_agent(self, message):
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": '''
                    You are an expert in identify the personality traits of your user.
                    Your response must be in json format with the following structure:
                        - analysis: provide a personality analysis of the user based on their answers to the questions. Do not simply summarize the answers, but provide a unique analysis of the user.
                        - news_topics: Should be a list of queries that are one or two words and be a good query parameter for calling a news API. Your topics should be derived from your analyis. Example formats: 2 words - Rock climbing - 1 word -AI
                        '''
                    },
                    {
                'role': 'user',
                'content': f'''{message}''',
                }
                
            ],
            response_format={ "type": "json_object" },
        )
        return response.choices[0].message.content

    def pass_to_vision_model(self, new_chat_history, chat_id, save_callback=None):
        response = self.openai_client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=new_chat_history,
            stream=True,
        )
        completed_response = ''
        inside_code_block = False
        language = None
        ignore_next_token = False
        
        for chunk in response:
            response_chunk = chunk.choices[0].delta.content
            if response_chunk is not None:
                completed_response, inside_code_block, language, ignore_next_token = self.process_response_chunk(
                    chat_id, response_chunk, completed_response, inside_code_block, language, ignore_next_token
                )
        # Notify the client that the stream is over
        end_stream_obj = {
            'message_from': 'agent',
            'content': completed_response,
            'type': 'end_of_stream',
        }
        emit('chat_response', end_stream_obj, room=chat_id)
        if save_callback:
            save_callback(chat_id, completed_response)