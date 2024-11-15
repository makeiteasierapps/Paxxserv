from fastapi import HTTPException
from app.services.ColbertService import ColbertService
from app.agents.SystemAgent import SystemAgent
from app.services.System.SystemService import SystemService

async def file_router(sio, sid, data, system_state_manager):
    uid = data.get('userMessage').get('uid')
    query = data.get('userMessage').get('content')
    
    try:
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
        relevant_files = [file for file in relevant_files if file['path'] in relevant_file_paths]
        await sio.emit('context_files', {'files': relevant_files}, room=sid)

    except HTTPException as e:
        error_message = f"Unauthorized access: {str(e)}"
        await sio.emit('error', {'message': error_message}, room=sid)
        return

def prep_data(data):
    return ''.join([f"# {item['path']}\n{item['content']}\n" for item in data])

async def get_agent_response(sio, sid, data, system_state_manager):
    distilled_data = prep_data(data['context'])
    print(distilled_data)
    await sio.emit('agent_response', {'response': distilled_data}, room=sid)

def setup_system_agent_handlers(sio, system_state_manager):
    @sio.on('file_router')
    async def file_router_handler(sid, data):
        await file_router(sio, sid, data, system_state_manager)

    @sio.on('get_agent_response')
    async def get_agent_response_handler(sid, data):
        await get_agent_response(sio, sid, data, system_state_manager)
