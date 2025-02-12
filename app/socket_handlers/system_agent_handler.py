import logging
from app.services.ChatService import ChatService
from app.agents.SystemAgent import SystemAgent
from app.agents.BossAgent import BossAgent, BossAgentConfig
from app.agents.OpenAiClient import OpenAiClient
from app.services.System.SystemService import SystemService
from app.services.context_processor import process_chat_context

def create_system_agent(sio, db, uid):
    ai_client = OpenAiClient(db, uid)
    system_boss_agent = BossAgent(BossAgentConfig(ai_client, sio, event_name='system_chat_response'))
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

def validate_chat_settings(data):
    chat_settings = data.get('selectedChat')
    if not chat_settings:
        raise ValueError("Chat settings are missing")
    return chat_settings

async def run_system_agent(sio, sid, data, system_state_manager, mongo_client):
    try:
        # Get and validate settings
        chat_settings = validate_chat_settings(data)
        uid, chat_id, context = chat_settings.get('uid'), chat_settings.get('chatId'), chat_settings.get('context', [])
        user_message = chat_settings.get('messages', [])[-1] if chat_settings.get('messages') else None
        # Initialize services and get relevant files
        db = mongo_client.db
        chat_service = ChatService(db, chat_type='system')
        relevant_files = await handle_file_routing(sio, sid, user_message.get('content'), uid, system_state_manager)
        
        # Update context with relevant files
        context.extend([
            {'type': 'file', 'path': f['path'], 'name': f['path'].split('/')[-1], 'content': f['content']}
            for f in relevant_files
        ])

        # Update chat settings and notify client
        await chat_service.create_message(chat_id, 'user', user_message.get('content'))
        await chat_service.update_settings(chat_id, context=context)
        await sio.emit('chat_settings_updated', {'chat_id': chat_id, 'context': context}, room=sid)

        # Process message with system agent
        system_agent = create_system_agent(sio, db, uid)
        await process_chat_context(db, uid, chat_id, context, user_message, chat_service, chat_settings, system_agent)
        await system_agent.process_message(
            chat_settings['messages'], 
            chat_id, 
            lambda cid, msg: chat_service.create_message(cid, 'agent', msg)
        )

    except Exception as e:
        logging.error('Error in run_system_agent: %s', str(e))
        await sio.emit('error', {'message': f"Error processing request: {str(e)}"}, room=sid)

def setup_system_agent_handlers(sio, system_state_manager, mongo_client):
    @sio.on('system_chat_response')
    async def get_agent_response_handler(sid, data):
        await run_system_agent(sio, sid, data, system_state_manager, mongo_client)
