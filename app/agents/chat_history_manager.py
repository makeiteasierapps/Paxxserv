from abc import ABC, abstractmethod
from typing import List, Dict
from app.utils.token_counter import token_counter


class ChatHistoryManager(ABC):
    @abstractmethod
    def process_history(self, chat_history: List[Dict]) -> List[Dict]:
        """
        Process and potentially update the incoming chat history.
        For example, you may reformat the messages, enforce token limits,
        or even summarize earlier conversation parts.
        """
        pass

class DefaultChatHistoryManager(ChatHistoryManager):
    """
    This is the default strategy which simply formats the messages.
    It enforces a token limit and handles images if present.
    """
    def __init__(self, token_limit: int = 20000):
        self.token_limit = token_limit
        self.token_counter = token_counter


    def process_history(self, chat_history: List[Dict]) -> List[Dict]:
        formatted_messages = []
        token_count = 0

        for message in chat_history:
            if token_count > self.token_limit:
                break

            content = message['content']
            role = 'user' if message.get('message_from') == 'user' else 'assistant'

            if role == 'user' and 'images' in message:
                content = self._format_message_with_images(message)
            elif role == 'assistant':
                content = message['content'][0]['content']

            # Fix the problematic condition to properly handle different content types
            if isinstance(content, str):
                token_count += self.token_counter(content)
            elif isinstance(content, list) and content and isinstance(content[0], dict) and 'content' in content[0]:
                token_count += self.token_counter(content[0]['content'])
            elif isinstance(content, list) and content:
                # Fallback for other list structures
                token_count += self.token_counter(str(content))
            else:
                # Safe fallback for any other content type
                token_count += self.token_counter(str(content))
                
            formatted_message = {"role": role, "content": content}
            formatted_messages.append(formatted_message)
            
        return formatted_messages

    def get_system_and_last_user_message(self, chat_history: List[Dict]) -> List[Dict]:
        """
        Returns a list containing only the system message (if present) and the last user message.
        """
        processed_history = self.process_history(chat_history)
        result = []
        
        # Find last user message
        last_user_message = next((msg for msg in reversed(processed_history) if msg['role'] == 'user'), None)
        if last_user_message:
            result.append(last_user_message)
            
        return result

    def _format_message_with_images(self, message: Dict) -> List[Dict]:
        return [
            {"type": "text", "text": message['content']},
            *[{"type": "image_url", "image_url": {"url": img['url']}} 
              for img in message.get('images', [])]
        ]

class SummarizingChatHistoryManager(ChatHistoryManager):
    """
    This strategy first uses a base manager for initial formatting.
    If the history grows too long, it uses a provided 'summarizer' 
    to collapse old messages into a summary.
    """
    def __init__(self, summarizer, base_manager: ChatHistoryManager):
        self.summarizer = summarizer
        self.base_manager = base_manager


    def process_history(self, chat_history: List[Dict]) -> List[Dict]:
        processed_history = self.base_manager.process_history(chat_history)
        if len(processed_history) > 10:
            summary = self.summarizer(processed_history[:-5])
            processed_history = [
                {"role": "assistant", "content": summary}
            ] + processed_history[-5:]
        return processed_history