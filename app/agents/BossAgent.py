import os
import tiktoken
from flask_socketio import emit
from app.agents.OpenAiClientBase import OpenAiClientBase

class BossAgent(OpenAiClientBase):
    def __init__(self, model='gpt-3.5-turbo', system_prompt="You are a friendly but genuine AI Agent. Don't be annoyingly nice, but don't be rude either.", chat_constants=None, user_analysis=None, db=None, uid=None):
        super().__init__(db, uid)
        self.is_initialized = True
        self.model = model
        self.system_prompt = system_prompt
        self.chat_constants = chat_constants
        self.user_analysis = user_analysis
    
    # rename to handle streamingResponse and make every step its own function
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
# return response chunks and start new function with below code
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
            inside_code_block = True
        elif response_chunk == '``' and language != 'markdown':
            inside_code_block = False
            ignore_next_token = True
        else:
            if inside_code_block and language is None:
                language = response_chunk.strip()
                if language == 'markdown':
                    inside_code_block = False
                    response_chunk = ''
                    language = None
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
                        "image_url": {"url": image_url}
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
