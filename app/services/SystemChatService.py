from app.services.context_processor import process_chat_context
from app.services.ChatService import ChatService
from app.services.ExtractionService import ExtractionService
from app.services.providers import ChatExtractionProvider, ChatSettingsProvider
from app.services.ContextManagerService import ContextManagerService
class SystemChatService:
    def __init__(self, db, sio):
        self.db = db
        self.sio = sio
        self.chat_service = ChatService(self.db, chat_type='system')

    async def setup_chat_context(self, chat_id, uid, relevant_files):
        context_files = [
            {
                'type': 'file', 
                'path': file['path'], 
                'name': file['path'].split('/')[-1], 
                'content': file['content']
            }
            for file in relevant_files
        ]
        
        await self.chat_service.update_settings(chat_id, context=context_files)
        return context_files

    async def notify_context_update(self, chat_id, context_files, sid):
        await self.sio.emit('chat_settings_updated', {
            'chat_id': chat_id,
            'context': context_files
        }, room=sid)

    async def process_system_context(self, uid, chat_id, context_files, user_message):
        extraction_service = ExtractionService(self.db, uid)
        extraction_provider = ChatExtractionProvider(extraction_service)
        settings_provider = ChatSettingsProvider(self.chat_service, chat_id)
        
        context_manager = ContextManagerService(
            extraction_provider=extraction_provider,
            settings_provider=settings_provider
        )
        
        context_results = await context_manager.process_context(
            context_files, 
            {'content': user_message}
        )
        return context_results.get('file', '')