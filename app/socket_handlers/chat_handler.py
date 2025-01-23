import json
import sys
import traceback
from app.services.ChatService import ChatService
from app.services.ExtractionService import ExtractionService
from app.services.ContextManagerService import ContextManagerService
from app.services.ProfileService import ProfileService
from app.agents.BossAgent import BossAgent
from app.agents.AnthropicClient import AnthropicClient
from app.agents.OpenAiClient import OpenAiClient
from app.services.MongoDbClient import MongoDbClient
from app.services.ColbertService import ColbertService
from app.services.providers import ChatExtractionProvider, ChatSettingsProvider

def get_db():
    try:
        mongo_client = MongoDbClient.get_instance('paxxium')
        return mongo_client.db
    except Exception as e:
        raise Exception(f"Database connection failed: {str(e)}")

def initialize_services(db, uid):
    chat_service = ChatService(db)
    profile_service = ProfileService(db, uid)
    return chat_service, profile_service

def create_boss_agent(chat_settings, sio, db, uid, profile_service):
    if not chat_settings:
        return None

    system_message = chat_settings.get('system_message', '')
    use_profile_data = chat_settings.get('use_profile_data', False)
    model = chat_settings.get('agent_model')
    user_analysis = profile_service.get_user_analysis(uid) if use_profile_data else None

    if model.startswith('claude'):
        ai_client = AnthropicClient(db, uid)
    else:
        ai_client = OpenAiClient(db, uid)

    boss_agent = BossAgent(
        ai_client,
        sio,
        model=model,
        system_message=system_message,
        user_analysis=user_analysis,
    )

    return boss_agent

async def handle_chat(sio, sid, data):
    try:
        chat_settings = data.get('selectedChat', None)
        if not chat_settings:
            await sio.emit('error', {"error": "Chat settings are missing"})
            return

        uid = chat_settings.get('uid')
        chat_id = chat_settings.get('chatId')
        messages = chat_settings.get('messages', [])
        context = chat_settings.get('context', [])
        if not uid or not chat_id or not messages:
            await sio.emit('error', {"error": "Missing required chat parameters"})
            return
            
        user_message = messages[0] if messages else None
        if not user_message:
            await sio.emit('error', {"error": "Message content is missing"})
            return

        db = get_db()
        chat_service, profile_service = initialize_services(db, uid)
        boss_agent = create_boss_agent(chat_settings, sio, db, uid, profile_service)

        await chat_service.create_message(chat_id, 'user', user_message)
        
        async def save_agent_message(chat_id, message):
            await chat_service.create_message(chat_id, 'agent', message)

        if context:
            extraction_service = ExtractionService(db, uid)
            extraction_provider = ChatExtractionProvider(extraction_service)
            settings_provider = ChatSettingsProvider(chat_service, chat_id)
            
            context_manager = ContextManagerService(
                extraction_provider=extraction_provider,
                settings_provider=settings_provider
            )
            
            context_results = await context_manager.process_context(context, user_message)
            if context_results.get('user_message'):
                chat_settings['messages'][0] = context_results['user_message']
            
            if context_results.get('system_context'):
                boss_agent.system_message += "\n" + context_results['system_context']

        await boss_agent.process_message(chat_settings['messages'], chat_id, save_agent_message)

    except Exception as e:
        # Get the full stack trace
        exc_type, exc_value, exc_traceback = sys.exc_info()
        stack_trace = traceback.format_exception(exc_type, exc_value, exc_traceback)
        
        error_details = {
            "error": str(e),
            "type": exc_type.__name__,
            "stack_trace": stack_trace,
            "location": "handle_chat"
        }
        print(f"Error details: {json.dumps(error_details, indent=2)}")
        await sio.emit('error', error_details)

def setup_chat_handlers(sio):
    @sio.on('chat')
    async def chat_handler(sid, data):
        await handle_chat(sio, sid, data)