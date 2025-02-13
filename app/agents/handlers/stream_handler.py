from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, AsyncIterator
import logging

class MessageType(Enum):
    TEXT = "text"
    CODE = "code"
    END_OF_STREAM = "end_of_stream"

@dataclass
class StreamState:
    inside_code_block: bool = False
    language: Optional[str] = None
    ignore_next_token: bool = False
    buffer: str = ""
    final_tool_calls: dict = field(default_factory=dict)

class StreamHandler:
    def __init__(self, sio, event_name):
        self.sio = sio
        self.event_name = event_name

    async def process_stream(self, chat_id: str, response: AsyncIterator) -> List[Dict]:
        response_chunks = []
        stream_state = StreamState()
        
        for chunk in response:
            await self._handle_chunk(chunk, chat_id, response_chunks, stream_state)
        
        # If we accumulated any tool calls, return both tool calls and response chunks
        if stream_state.final_tool_calls:
            return {
                'tool_calls': list(stream_state.final_tool_calls.values()),
                'response_chunks': response_chunks
            }
        
        return response_chunks

    async def _handle_chunk(self, chunk: Any, chat_id: str, response_chunks: List, stream_state: StreamState):
        if hasattr(chunk, 'type'):
            await self._handle_anthropic_chunk(chunk, chat_id, response_chunks, stream_state)
        else:
            await self._handle_openai_chunk(chunk, chat_id, response_chunks, stream_state)

    async def _handle_anthropic_chunk(self, chunk: Any, chat_id: str, response_chunks: List, stream_state: StreamState):
        if chunk.type == 'message_start':
            logging.debug('Stream message start')
        elif chunk.type == 'message_stop':
            logging.debug('Stream message end')
        elif chunk.type == 'content_block_delta':
            if chunk.delta.type == 'text_delta':
                await self._process_response_chunk(chat_id, chunk.delta.text, response_chunks, stream_state)
        elif chunk.type == 'message_delta':
            pass  # Handle message delta if needed

    async def _handle_openai_chunk(self, chunk: Any, chat_id: str, response_chunks: List, stream_state: StreamState):
        # Handle tool calls if present
        if hasattr(chunk.choices[0].delta, 'tool_calls'):
            for tool_call in chunk.choices[0].delta.tool_calls or []:
                index = tool_call.index
                if index not in stream_state.final_tool_calls:
                    stream_state.final_tool_calls[index] = tool_call
                else:
                    # Append arguments as they stream in
                    stream_state.final_tool_calls[index].function.arguments += tool_call.function.arguments

        # Handle content if present
        response_chunk = chunk.choices[0].delta.content
        if response_chunk is not None:
            await self._process_response_chunk(chat_id, response_chunk, response_chunks, stream_state)

    async def _process_response_chunk(self, chat_id: str, response_chunk: str, response_chunks: List, stream_state: StreamState):
        if stream_state.ignore_next_token:
            stream_state.ignore_next_token = False
            return

        if response_chunk == '```':
            stream_state.inside_code_block = not stream_state.inside_code_block
            if stream_state.inside_code_block:
                stream_state.buffer = ''
            else:
                stream_state.language = None
            return

        if stream_state.inside_code_block and not stream_state.language:
            stream_state.buffer += response_chunk
            if '\n' in stream_state.buffer:
                language, code = stream_state.buffer.split('\n', 1)
                stream_state.language = language.strip()
                if code:
                    await self._handle_chunk_content(chat_id, code, response_chunks, stream_state)
                stream_state.buffer = ''
            return

        if response_chunk == '``':
            stream_state.inside_code_block = False
            stream_state.language = None
            stream_state.ignore_next_token = True
        else:
            await self._handle_chunk_content(chat_id, response_chunk, response_chunks, stream_state)

    async def _handle_chunk_content(self, chat_id: str, response_chunk: str, response_chunks: List, stream_state: StreamState):
        formatted_message = {
            'type': MessageType.CODE.value if stream_state.inside_code_block else MessageType.TEXT.value,
            'content': response_chunk,
            'room': chat_id
        }
        
        if stream_state.inside_code_block:
            formatted_message['language'] = stream_state.language or 'markdown'
            
        response_chunks.append(formatted_message)
        logging.debug('Formatted message: %s', formatted_message)
        await self.sio.emit(self.event_name, formatted_message)

    def collapse_response_chunks(self, response_chunks: List[Dict]) -> List[Dict]:
        collapsed_response = []
        if response_chunks:
            current_message = response_chunks[0].copy()
            for chunk in response_chunks[1:]:
                if chunk['type'] == current_message['type']:
                    current_message['content'] += chunk['content']
                else:
                    collapsed_response.append(current_message)
                    current_message = chunk.copy()
            collapsed_response.append(current_message)
        return collapsed_response
