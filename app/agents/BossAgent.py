from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Any, Dict, Union
import logging
from app.agents.OpenAiClient import OpenAiClient
from app.agents.AnthropicClient import AnthropicClient
from app.utils.token_counter import token_counter
from app.agents.handlers.stream_handler import StreamHandler
from app.agents.chat_history_manager import ChatHistoryManager, DefaultChatHistoryManager

logger = logging.getLogger(__name__)

class MessageType(Enum):
    END_OF_STREAM = "end_of_stream"

class Role(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    DEVELOPER = "developer"

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
    stream_response: bool = True

class AIResponseGenerator:
    """
    Helper class that encapsulates the logic for calling the appropriate
    AI client to generate a response. Different agents may use different strategies.
    """
    def __init__(self, ai_client: Any, model: str, stream_response: bool, tools: Optional[List[Dict]] = None):
        self.ai_client = ai_client
        self.model = model
        self.stream_response = stream_response
        self.tools = tools

    async def generate_response(self, messages: List[Dict]) -> Any:
        if isinstance(self.ai_client, OpenAiClient):
            return await self.ai_client.generate_chat_completion(
                messages,
                model=self.model,
                stream=self.stream_response,
            )
        elif isinstance(self.ai_client, AnthropicClient):
            return await self.ai_client.generate_chat_completion(
                messages=messages[1:],  # Exclude system message
                model=self.model,
                stream=True,
                system=messages[0]['content']
            )
        else:
            raise ValueError("Unsupported AI client type")

class BossAgent:
    """
    The BossAgent ties together the various components:
    • The AIResponseGenerator (to communicate with the AI service)
    • The chat history manager (to pre-process the conversation)
    • Handler for streaming responses
    """
    def __init__(self, config: BossAgentConfig, chat_history_manager: ChatHistoryManager = None):
        self.ai_client = config.ai_client
        self.sio = config.sio
        self.model = config.model
        self.system_message = config.system_message
        self.user_analysis = config.user_analysis
        self.context_urls = config.context_urls
        self.event_name = config.event_name
        self.stream_response = config.stream_response
        self.image_path = None

        # Initialize handler
        self.stream_handler = StreamHandler(config.sio, config.event_name)
        
        # Use provided ChatHistoryManager or default
        self.chat_history_manager = chat_history_manager or DefaultChatHistoryManager()
        
        # Initialize AI response generator
        self.ai_response_generator = AIResponseGenerator(
            ai_client=self.ai_client,
            model=self.model,
            stream_response=self.stream_response,
        )

    async def process_message(self, chat_history: List[Dict], chat_id: str, save_callback=None):
        """
        Main entry point for processing messages. The chat_history is processed by 
        the ChatHistoryManager strategy, then an AI response is generated.
        """
        formatted_messages = self.chat_history_manager.process_history(chat_history)
        return await self._get_ai_response(chat_id, formatted_messages, save_callback)

    async def _get_ai_response(self, chat_id: str, formatted_messages: List[Dict], save_callback=None):
        """Generate and process AI response"""
        system_content = self._create_system_content()
        message_role = Role.DEVELOPER.value if any(model in self.model.lower() for model in ['o1', 'o3-mini']) else Role.SYSTEM.value
        messages = [{"role": message_role, "content": system_content}, *formatted_messages]
        final_response = None
        
        try:
            response = await self.ai_response_generator.generate_response(messages)
            stream_result = await self.stream_handler.process_stream(chat_id, response)
            final_response = self.stream_handler.collapse_response_chunks(stream_result)
            
            await self._send_end_of_stream(chat_id, 
                stream_result['response_chunks'] if isinstance(stream_result, dict) else stream_result
            )
            
        finally:
            if save_callback and final_response:
                await save_callback(chat_id, final_response)
        
        return final_response

    def _create_system_content(self) -> str:
        formatting_message = "Formatting re-enabled\n" if any(model in self.model.lower() for model in ['o1', 'o3-mini']) else ""
        return f'''
            {formatting_message}
            {self.system_message}
        '''

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