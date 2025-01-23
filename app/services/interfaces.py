from abc import ABC, abstractmethod
from typing import List, Dict

class ExtractionProvider(ABC):
    @abstractmethod
    async def extract_from_url(self, url: str, method: str, for_kb: bool) -> List[Dict]:
        pass
    
    @abstractmethod
    def parse_extraction_response(self, docs: List[Dict]) -> Dict:
        pass

class SettingsProvider(ABC):
    @abstractmethod
    async def update_settings(self, **kwargs) -> None:
        pass