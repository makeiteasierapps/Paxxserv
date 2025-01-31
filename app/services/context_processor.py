from app.services.providers import ChatExtractionProvider, ChatSettingsProvider
from app.services.ExtractionService import ExtractionService
from app.services.ContextManagerService import ContextManagerService

async def process_chat_context(db, uid, chat_id, context, user_message, chat_service, chat_settings, agent):
    if not context:
        return
        
    extraction_service = ExtractionService(db, uid)
    extraction_provider = ChatExtractionProvider(extraction_service)
    settings_provider = ChatSettingsProvider(chat_service, chat_id)
    await settings_provider.update_settings(context=context)
    
    context_manager = ContextManagerService(
        extraction_provider=extraction_provider,
        settings_provider=settings_provider
    )
    
    context_results = await context_manager.process_context(context, user_message)
    if context_results.get('user_message'):
        chat_settings['messages'][0] = context_results['user_message']
    
    if context_results.get('system_context'):
        agent.system_message += "\n" + context_results['system_context']