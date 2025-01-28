from fastapi import HTTPException
from app.services.ColbertService import ColbertService
from app.services.ChatService import ChatService
from app.agents.SystemAgent import SystemAgent
from app.agents.BossAgent import BossAgent
from app.agents.OpenAiClient import OpenAiClient
from app.services.MongoDbClient import MongoDbClient
from app.services.System.SystemService import SystemService

def get_db():
    try:
        mongo_client = MongoDbClient.get_instance('paxxium')
        return mongo_client.db
    except Exception as e:
        raise Exception(f"Database connection failed: {str(e)}")

def prep_data(data):
    return ''.join([f"# {item['path']}\n{item['content']}\n" for item in data])

def create_system_agent(sio, db, uid, system_message):
    ai_client = OpenAiClient(db, uid)
    system_boss_agent = BossAgent(ai_client, sio, event_name='system_chat_response', system_message=system_message)
    return system_boss_agent

async def handle_file_routing(sio, sid, query, uid, system_state_manager):
    system_service = SystemService(system_state_manager, uid)
    system_agent = SystemAgent()
    category_list = await system_service.get_config_categories()
    categories = system_agent.category_routing(query, ', '.join(category_list))
    
    relevant_files = []
    for category in categories:
        category_files = await system_service.get_config_files_by_category(category)
        relevant_files.extend(category_files)
    
    relevant_file_paths = ', '.join([file['path'] for file in relevant_files])
    relevant_file_paths = system_agent.file_routing(query, relevant_file_paths)
    return [file for file in relevant_files if file['path'] in relevant_file_paths]

async def run_system_agent(sio, sid, data, system_state_manager):
    try:
        chat_settings = data.get('selectedChat', None)
        if not chat_settings:
            await sio.emit('error', {"error": "Chat settings are missing"})
            return
        uid = chat_settings.get('uid')
        chat_id = chat_settings.get('chatId')
        messages = chat_settings.get('messages', [])
        user_message = messages[0].get('content') if messages else None
        system_agent = SystemAgent()
        relevant_files = await handle_file_routing(sio, sid, user_message, uid, system_state_manager)
        db = get_db()
        chat_service = ChatService(db, chat_type='system')
        await chat_service.create_message(chat_id, 'user', user_message)
        async def save_agent_message(chat_id, message):
            await chat_service.create_message(chat_id, 'agent', message)
        
        distilled_data = prep_data(relevant_files)
        system_agent = create_system_agent(sio, db, uid, distilled_data)
        await system_agent.process_message(chat_settings['messages'], chat_id, save_agent_message)
            
    except HTTPException as e:
        error_message = f"Unauthorized access: {str(e)}"
        await sio.emit('error', {'message': error_message}, room=sid)

def setup_system_agent_handlers(sio, system_state_manager):
    @sio.on('system_chat_response')
    async def get_agent_response_handler(sid, data):
        await run_system_agent(sio, sid, data, system_state_manager)
