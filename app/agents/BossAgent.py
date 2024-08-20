import tiktoken
from flask_socketio import emit
from app.agents.OpenAiClient import OpenAiClient
from app.agents.AnthropicClient import AnthropicClient

class BossAgent():
    def __init__(self, ai_client, model='gpt-4o-mini', system_prompt="You are a friendly but genuine AI Agent. Don't be annoyingly nice, but don't be rude either.", chat_constants=None, user_analysis=None):
        self.ai_client = ai_client
        self.is_initialized = True
        self.model = model
        self.system_prompt = system_prompt
        self.chat_constants = chat_constants
        self.user_analysis = user_analysis
    
    def handle_streaming_response(self, chat_id, new_chat_history, save_callback=None, system_message=None):
        system_content = f'''
            {self.system_prompt}
            ***USER ANALYSIS***
            {self.user_analysis}
            **************
            ***THINGS TO REMEMBER***
            {self.chat_constants}
            **************
        '''
        if system_message:
            system_content += f"\n{system_message}"
        
        if isinstance(self.ai_client, OpenAiClient):
            openai_messages = [{
                'role': 'system',
                'content': system_content
            }, *new_chat_history]
            response = self.ai_client.generate_chat_completion(openai_messages, model=self.model, stream=True)
        elif isinstance(self.ai_client, AnthropicClient):
            response = self.ai_client.generate_chat_completion(messages=new_chat_history, model=self.model, stream=True, system=system_content)
        
        response_chunks = self.process_streaming_response(chat_id, response)
        collapsed_response = self.collapse_response_chunks(response_chunks)
        self.send_end_of_stream_notification(chat_id, response_chunks)
        if save_callback:
            save_callback(chat_id, collapsed_response)
    
    def process_streaming_response(self, chat_id, response):
        response_chunks = []
        stream_state = {'inside_code_block': False, 'language': None, 'ignore_next_token': False, 'buffer': ''}

        for chunk in response:
            if hasattr(chunk, 'type'):
                if chunk.type == 'message_start':
                    print('Stream message start')
                elif chunk.type == 'message_stop':
                    print('Stream message end')
                elif chunk.type == 'content_block_delta':
                    delta = chunk.delta
                    if delta.type == 'text_delta':
                        self.process_response_chunk(chat_id, delta.text, response_chunks, stream_state)
                elif chunk.type == 'message_delta':
                    # Handle any top-level changes to the Message object if needed
                    pass
            else:  # OpenAI client structure
                response_chunk = chunk.choices[0].delta.content
                if response_chunk is not None:
                    self.process_response_chunk(chat_id, response_chunk, response_chunks, stream_state)

        return response_chunks

    def process_response_chunk(self, chat_id, response_chunk, response_chunks, stream_state):
        print(response_chunk)
        if stream_state.get('ignore_next_token', False):
            stream_state['ignore_next_token'] = False
            return

        if response_chunk == '```':
            stream_state['inside_code_block'] = not stream_state['inside_code_block']
            if stream_state['inside_code_block']:
                stream_state['buffer'] = ''
            else:
                stream_state['language'] = None
            return

        if stream_state['inside_code_block'] and not stream_state['language']:
            stream_state['buffer'] += response_chunk
            if '\n' in stream_state['buffer']:
                language, code = stream_state['buffer'].split('\n', 1)
                stream_state['language'] = language.strip()
                if code:
                    self.handle_chunk_content(chat_id, code, response_chunks, stream_state)
                stream_state['buffer'] = ''
            return

        if response_chunk == '``':
            stream_state['inside_code_block'] = False
            stream_state['language'] = None
            stream_state['ignore_next_token'] = True
        else:
            self.handle_chunk_content(chat_id, response_chunk, response_chunks, stream_state)
    
    def handle_chunk_content(self, chat_id, response_chunk, response_chunks, stream_state):
        formatted_message = self.format_stream_message(response_chunk, stream_state['inside_code_block'], stream_state['language'])
        formatted_message['room'] = chat_id
        response_chunks.append(formatted_message)
        emit('chat_response', formatted_message)

    def collapse_response_chunks(self, response_chunks):
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
        return collapsed_response

    def send_end_of_stream_notification(self, chat_id, response_chunks):
        end_stream_obj = {
            'message_from': 'agent',
            'content': response_chunks,
            'type': 'end_of_stream',
            'room': chat_id
        }
        emit('chat_response', end_stream_obj)

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
        self.handle_streaming_response(chat_id, new_chat_history, save_callback, system_message)
     
    def manage_chat(self, chat_history, new_user_message, image_url=None):
        """
        Takes a chat object extracts x amount of tokens and returns a message
        object ready to pass into OpenAI chat completion or Anthropic
        """
        
        formatted_messages = []
        token_limit = 20000
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
                "content": [
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
    
    def create_vector_pipeline(self, query, kb_id):
        embeddings = self.ai_client.embed_content(query)
        pipeline = [
            {
                '$vectorSearch': {
                    'index': 'personal-kb',
                    'path': 'values',
                    'queryVector': embeddings,
                    'numCandidates': 100,
                    'limit': 5,
                    'filter': {
                        'kb_id': kb_id
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
    
    def prepare_url_content_for_ai(self, url_content, system_prompt=None):
        query_instructions = f'''
        \nAnswer the users question using the content from the url they are interested in.
        URL: {url_content['source_url']}
        CONTENT: {url_content['content']}
        \n
        '''

        if system_prompt:
            query_instructions += f"\n{system_prompt}"
        
        system_message = {
            'role': 'system',
            'content': query_instructions
        }
        return system_message
    
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
