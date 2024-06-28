import os
import tiktoken
from openai import OpenAI
import dspy
from dspy import Signature, InputField, OutputField
from dspy.functional import TypedPredictor
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv

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

    def __init__(self, openai_key=None, model='gpt-3.5-turbo'):
        if not hasattr(self, 'is_initialized'):
            self.is_initialized = True
            self.openai_key = openai_key or self._load_openai_key()
            self.model = model if model == 'gpt-4-turbo' else 'gpt-3.5-turbo'
            self.lm = None
            self.client = dspy.OpenAI(api_key=self.openai_key)  
            self.openai_client = OpenAI(api_key=self.openai_key)
            self.user_analysis = ""

    def _load_openai_key(self):
        load_dotenv()
        return os.getenv('OPENAI_API_KEY')

    def _initialize_dspy(self):
        if self.lm is None:
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
    
    def pass_to_boss_agent(self, new_chat_history):
    
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=new_chat_history,
            stream=True,
        )
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                stream_obj = {
                    'message_from': 'agent',
                    'content': chunk.choices[0].delta.content,
                    'type': 'stream',
                }
                yield stream_obj

    def get_full_response(self, message):
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": message,
            }],
        )
        print('Sam', response.choices[0].message.content)
        return response.choices[0].message.content
    
    def stream_audio_response(self, message):
        file_path = 'audio.mp3'
        
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
 
    def manage_chat(self, chat_history, new_user_message):
        """
        Takes a chat object extracts x amount of tokens and returns a message
        object ready to pass into OpenAI chat completion
        """

        new_name = []
        token_limit = 2000
        token_count = 0
        for message in chat_history:
            if token_count > token_limit:
                break
            if message['message_from'] == 'user':
                token_count += self.token_counter(message['content'])
                new_name.append({
                    "role": "user",
                    "content": message['content'],
                })
            else:
                token_count += self.token_counter(message['content'])
                new_name.append({
                    "role": "assistant",
                    "content": message['content'],
                })
        new_name.append({
            "role": "user",
            "content": new_user_message,
        })
        
        return new_name
    
    def process_message(self, chat_id, chat_history, user_message, system_message=None):
    
        new_chat_history = self.manage_chat(chat_history, user_message)
        if system_message:
            new_chat_history.insert(0, system_message)
        
        for response_chunk in self.pass_to_boss_agent(new_chat_history):
            response_chunk['chat_id'] = chat_id
            yield response_chunk

    def prepare_vector_response(self, query_results):
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