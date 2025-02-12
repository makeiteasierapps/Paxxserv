from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, Union, Mapping, Callable
import logging
from app.agents.OpenAiClient import OpenAiClient
from app.agents.AnthropicClient import AnthropicClient
from app.utils.token_counter import token_counter
from app.agents.handlers.stream_handler import StreamHandler
from app.agents.handlers.function_handler import FunctionHandler
from fastapi import FastAPI
logger = logging.getLogger(__name__) 

class MessageType(Enum):
    END_OF_STREAM = "end_of_stream"

class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

@dataclass
class Message:
    content: Union[str, List[Dict]]
    role: Role
    type: Optional[MessageType] = None
    language: Optional[str] = None
    room: Optional[str] = None

@dataclass
class BossAgentConfig:
    ai_client: Any
    sio: Any
    model: str = 'gpt-4o-mini'
    system_message: str = ''
    user_analysis: Optional[str] = None
    context_urls: Optional[List[str]] = None
    event_name: str = 'chat_response'
    tools: Optional[List[Dict]] = None
    tool_choice: Optional[str] = None
    stream_response: bool = True
    function_map: Mapping[str, Callable] = field(default_factory=dict)

class BossAgent:
    def __init__(self, config: BossAgentConfig):
        self.ai_client = config.ai_client
        self.sio = config.sio
        self.model = config.model
        self.system_message = config.system_message
        self.user_analysis = config.user_analysis
        self.context_urls = config.context_urls
        self.stream_handler = StreamHandler(config.sio, config.event_name)
        self.function_handler = FunctionHandler(config.function_map)
        self.token_counter = token_counter
        self.tools = config.tools
        self.tool_choice = config.tool_choice
        self.stream_response = config.stream_response
        self.image_path = None
        self.event_name = config.event_name

    async def process_message(self, chat_history: List[Dict], chat_id: str, save_callback=None):
        """Main entry point for processing messages"""
        formatted_messages = self._format_chat_history(chat_history)
        return await self._get_ai_response(chat_id, formatted_messages, save_callback)

    def _format_chat_history(self, chat_history: List[Dict]) -> List[Dict]:
        """Format chat history with token limiting"""
        formatted_messages = []
        token_count = 0
        token_limit = 20000

        for message in chat_history:
            if token_count > token_limit:
                break

            content = message['content']
            role = Role.USER.value if message['message_from'] == 'user' else Role.ASSISTANT.value
            
            if role == Role.USER.value and 'images' in message:
                content = self._format_message_with_images(message)
            elif role == Role.ASSISTANT.value:
                content = message['content'][0]['content']
            
            token_count += self.token_counter(content if isinstance(content, str) else content[0]['content'])
            formatted_messages.append({"role": role, "content": content})

        return formatted_messages

    def _format_message_with_images(self, message: Dict) -> List[Dict]:
        """Format message that contains images"""
        return [
            {"type": "text", "text": message['content']},
            *[{"type": "image_url", "image_url": {"url": img['url']}} 
              for img in message['images']]
        ]

    async def _get_ai_response(self, chat_id: str, formatted_messages: List[Dict], save_callback=None):
        """Generate and process AI response"""
        system_content = self._create_system_content()
        messages = [{"role": Role.SYSTEM.value, "content": system_content}, *formatted_messages]
        final_response = None
        
        try:
            response = await self._generate_ai_response(messages)
            # All responses are now streamed
            stream_result = await self.stream_handler.process_stream(chat_id, response)
            
            # Check if we got tool calls
            if isinstance(stream_result, dict) and 'tool_calls' in stream_result:
                formatted_messages.append({
                    "role": "assistant",
                    "tool_calls": stream_result['tool_calls']
                })

                conversation_messages = self.function_handler.process_function_calls(
                    stream_result['tool_calls'],
                    formatted_messages,
                    system_content,
                )

                func_response = await self.ai_client.generate_chat_completion(
                    conversation_messages,
                    model=self.model,
                    stream=True
                )
                response_chunks = await self.stream_handler.process_stream(chat_id, func_response)
                final_response = self.stream_handler.collapse_response_chunks(
                    response_chunks if isinstance(response_chunks, list) else response_chunks['response_chunks']
                )
            else:
                final_response = self.stream_handler.collapse_response_chunks(stream_result)
            
            await self._send_end_of_stream(chat_id, 
                stream_result['response_chunks'] if isinstance(stream_result, dict) else stream_result
            )
            
        finally:
            if save_callback and final_response:
                await save_callback(chat_id, final_response)
        
        return final_response

    def _create_system_content(self) -> str:
        """Create the system content message"""
        return f'''
            ***USER ANALYSIS***
            {self.user_analysis}
            **************
            ***THINGS TO REMEMBER***
            {self.system_message}
            **************
        '''

    async def _generate_ai_response(self, messages: List[Dict]):
        """Generate AI response with appropriate client"""
        if isinstance(self.ai_client, OpenAiClient):
            return await self.ai_client.generate_chat_completion(
                messages,
                model=self.model,
                stream=self.stream_response,
                tools=self.tools,
                tool_choice='auto'
            )
        elif isinstance(self.ai_client, AnthropicClient):
            return await self.ai_client.generate_chat_completion(
                messages=messages[1:],  # Exclude system message
                model=self.model,
                stream=True,
                system=messages[0]['content']
            )

    async def _send_end_of_stream(self, chat_id: str, response_chunks: List[Dict]):
        end_stream_obj = {
            'message_from': 'agent',
            'content': response_chunks,
            'type': MessageType.END_OF_STREAM.value,
            'room': chat_id,
            'image_path': self.image_path,
            'context_urls': self.context_urls
        }
        
        await self.sio.emit(self.event_name, end_stream_obj)