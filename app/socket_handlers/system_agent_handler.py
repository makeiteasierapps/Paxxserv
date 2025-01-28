from fastapi import HTTPException
from app.services.ColbertService import ColbertService
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
    system_boss_agent = BossAgent(ai_client, sio, event_name='system_response', system_message=system_message)
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
        uid = data.get('uid')
        query = data.get('content')
        system_agent = SystemAgent()
        requires_AI_response, needs_system_files = system_agent.query_classifier(query)
        
        relevant_files = []
        if needs_system_files:
            relevant_files = await handle_file_routing(sio, sid, query, uid, system_state_manager)
            await sio.emit('context_files', {'files': relevant_files}, room=sid)
        
        if requires_AI_response:
            db = get_db()
            distilled_data = prep_data(relevant_files)
            system_agent = create_system_agent(sio, db, uid, distilled_data)
            await system_agent.process_message([], sid)
            
    except HTTPException as e:
        error_message = f"Unauthorized access: {str(e)}"
        await sio.emit('error', {'message': error_message}, room=sid)

def setup_system_agent_handlers(sio, system_state_manager):
    @sio.on('get_agent_response')
    async def get_agent_response_handler(sid, data):
        await run_system_agent(sio, sid, data, system_state_manager)
