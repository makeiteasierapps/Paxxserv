from app.services.MongoDbClient import MongoDbClient
from app.services.UserService import UserService
from app.services.SystemService import SystemService
from app.agents.CategoryAgent import CategoryAgent

CATEGORIES = [
    "NGINX Configuration",
    "SystemD Service Files",
    "FSTAB for File System Mounting",
    "SSH Configuration",
    "DNS and Networking",
    "Logrotate for Log Management",
    "User and Group Configuration",
    "Sysctl for Kernel Parameters",
    "Environment Variables",
    "Fail2ban Configuration"
]
def get_db(db_name: str):
    try:
        mongo_client = MongoDbClient.get_instance(db_name)
        return mongo_client.db
    except Exception as e:
        raise Exception(f"Database connection failed: {str(e)}")

def get_system_service(data):
    db = get_db(data.get('dbName'))
    user_service = UserService(db)
    uid = data.get('uid')
    return SystemService(db, user_service, uid)

async def setup_file_system(sio, sid, data):
    system_service = get_system_service(data)
    filename = data.get('filename')

    try:
        await sio.emit('file_check_update', {'message': 'Checking if file exists...'}, room=sid)
        result = await system_service.check_if_config_file_exists_on_server(filename)
        await sio.emit('file_check_update', {'message': f'File exists: {result}'}, room=sid)

        if result:
            await sio.emit('file_check_update', {'message': 'Reading file content...'}, room=sid)
            content = await system_service.read_config_file(filename)
            
            await sio.emit('file_check_update', {'message': 'Categorizing file...'}, room=sid)
            category_agent = CategoryAgent()
            result_obj = category_agent.does_file_belong_in_category(filename, CATEGORIES)
            
            if result_obj["belongs"]:
                await sio.emit('file_check_result', {"exists": True, "content": content, "category": result_obj["category"]}, room=sid)
            else:
                await sio.emit('file_check_update', {'message': 'Creating new category...'}, room=sid)
                new_category = category_agent.create_new_category(filename)
                await sio.emit('file_check_result', {"exists": True, "content": content, "category": new_category}, room=sid)
        else:
            await sio.emit('file_check_result', {"exists": False}, room=sid)
    
    except Exception as e:
        await sio.emit('file_check_error', {'error': f"An error occurred: {str(e)}"}, room=sid)


def setup_file_system_handlers(sio):
    @sio.on('file_check')
    async def setup_file_system_handler(sid, data):
        await setup_file_system(sio, sid, data)