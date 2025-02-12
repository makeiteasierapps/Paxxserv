import asyncio
from app.services.System.SystemService import SystemService
from app.agents.CategoryAgent import CategoryAgent


async def get_system_service(data, system_state_manager) -> SystemService:
    uid = data.get('uid')
    service = SystemService(system_state_manager, uid)
    await service.initialize()
    return service

async def setup_file_system(sio, sid, data, system_state_manager):
    system_service = await get_system_service(data, system_state_manager)
    filename = data.get('filename')
    categories = system_service.system_manager.config_categories
    category_agent = CategoryAgent()

    try:
        await sio.emit('file_check_update', {'message': 'Checking if file exists...'}, room=sid)
        await asyncio.sleep(0.01)

        does_exist = await system_service.system_manager.check_if_config_file_exists_on_server(filename)
        
        await sio.emit('file_check_update', {'message': f'File exists: {does_exist}'}, room=sid)
        await asyncio.sleep(0.01)

        category, is_new_category = determine_category(category_agent, filename, categories)

        if does_exist:
            await sio.emit('file_check_update', {'message': 'Reading file content...'}, room=sid)
            await asyncio.sleep(0.01)
            content = await system_service.read_config_file(filename)
            
            if is_new_category:
                await sio.emit('file_check_update', {'message': 'Creating new category...', 'category': category}, room=sid)
                await asyncio.sleep(0.1)
                system_service.add_new_config_category(category, '', '', '')

            await sio.emit('file_check_result', {"exists": True, "path": filename, "content": content, "category": category}, room=sid)
        else:
            await sio.emit('file_check_result', {"exists": False, "path": filename, "category": category}, room=sid)

    except Exception as e:
        await sio.emit('file_check_error', {'error': f"An error occurred: {str(e)}"}, room=sid)

def determine_category(category_agent, filename, categories):
    result_obj = category_agent.does_file_belong_in_category(filename, categories)
    
    if result_obj["belongs"]:
        return result_obj["category"], False
    else:
        new_category = category_agent.create_new_category(filename)
        return new_category, True

def setup_file_system_handlers(sio, system_state_manager):
    @sio.on('file_check')
    async def setup_file_system_handler(sid, data):
        await setup_file_system(sio, sid, data, system_state_manager)