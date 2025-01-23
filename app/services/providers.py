from typing import List, Dict
from app.services.interfaces import ExtractionProvider, SettingsProvider
from app.services.ExtractionService import ExtractionService
from app.services.ChatService import ChatService

class ChatExtractionProvider(ExtractionProvider):
    def __init__(self, extraction_service: ExtractionService):
        self.extraction_service = extraction_service
    
    async def extract_from_url(self, url: str, method: str, for_kb: bool) -> List[Dict]:
        return await self.extraction_service.extract_from_url(url, method, for_kb)
    
    def parse_extraction_response(self, docs: List[Dict]) -> Dict:
        return self.extraction_service.parse_extraction_response(docs)

class ChatSettingsProvider(SettingsProvider):
    def __init__(self, chat_service: ChatService, chat_id: str):
        self.chat_service = chat_service
        self.chat_id = chat_id
    
    async def update_settings(self, **kwargs) -> None:
        await self.chat_service.update_settings(self.chat_id, **kwargs)