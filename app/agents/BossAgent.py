import base64
from app.agents.OpenAiClient import OpenAiClient
from app.agents.AnthropicClient import AnthropicClient
from app.utils.token_counter import token_counter

class BossAgent:
    def __init__(self, ai_client,  model='gpt-4o-mini',chat_constants=None, user_analysis=None, sio=None):
        self.ai_client = ai_client
        self.sio = sio
        self.is_initialized = True
        self.model = model
        self.chat_constants = chat_constants
        self.user_analysis = user_analysis
        self.image_path = None
        self.token_counter = token_counter

    async def handle_streaming_response(self, chat_id, new_chat_history, save_callback=None, system_message=None):
        system_content = f'''
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
        
        response_chunks = await self.process_streaming_response(chat_id, response)
        collapsed_response = self.collapse_response_chunks(response_chunks)
        await self.send_end_of_stream_notification(chat_id, response_chunks)
        if save_callback:
            await save_callback(chat_id, collapsed_response)
    
    async def process_streaming_response(self, chat_id, response):
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
                        await self.process_response_chunk(chat_id, delta.text, response_chunks, stream_state)
                elif chunk.type == 'message_delta':
                    # Handle any top-level changes to the Message object if needed
                    pass
            else:  # OpenAI client structure
                response_chunk = chunk.choices[0].delta.content
                if response_chunk is not None:
                    await self.process_response_chunk(chat_id, response_chunk, response_chunks, stream_state)

        return response_chunks

    async def process_response_chunk(self, chat_id, response_chunk, response_chunks, stream_state):
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
            await self.handle_chunk_content(chat_id, response_chunk, response_chunks, stream_state)
    
    async def handle_chunk_content(self, chat_id, response_chunk, response_chunks, stream_state):
        formatted_message = self.format_stream_message(response_chunk, stream_state['inside_code_block'], stream_state['language'])
        formatted_message['room'] = chat_id
        response_chunks.append(formatted_message)
        if self.sio:
            await self.sio.emit('chat_response', formatted_message)

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

    async def send_end_of_stream_notification(self, chat_id, response_chunks):
        end_stream_obj = {
            'message_from': 'agent',
            'content': response_chunks,
            'type': 'end_of_stream',
            'room': chat_id,
            'image_path': self.image_path
        }
        
        if self.sio:
            await self.sio.emit('chat_response', end_stream_obj)

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

    async def process_message(self, chat_history, chat_id, user_message, system_message=None, save_callback=None, image_blob=None):
        new_chat_history = self.manage_chat(chat_history, user_message, image_blob)
        await self.handle_streaming_response(chat_id, new_chat_history, save_callback, system_message)
     
    def manage_chat(self, chat_history, new_user_message, image_blob=None):
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

        if image_blob:
            base64_image = base64.b64encode(image_blob).decode('utf-8')
            formatted_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text", 
                        "text": new_user_message
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    },
                ],
            })
        else:
            formatted_messages.append({
                "role": "user",
                "content": new_user_message,
            })
        
        return formatted_messages

    def prepare_url_content_for_ai(self, url_content):
        query_instructions = f'''
        \nAnswer the users question using the content from the url they are interested in.
        URL: {url_content['source_url']}
        CONTENT: {url_content['content']}
        \n
        '''
        
        system_message = {
            'role': 'system',
            'content': query_instructions
        }
        return system_message
    
    
