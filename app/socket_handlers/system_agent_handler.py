from fastapi import HTTPException
from app.services.MongoDbClient import MongoDbClient
from app.services.ColbertService import ColbertService
from app.agents.SystemAgent import SystemAgent
from app.services.System.SystemService import SystemService

async def handle_system_agent(sio, sid, data):
    uid = data.get('userMessage').get('uid')
    query = data.get('userMessage').get('content')
    
    db = get_db()
    try:
        system_service = SystemService(db, uid)
        system_agent = SystemAgent()
        categories = system_agent.category_routing(query, ','.join(system_service.config_categories.keys()))
        
        relevant_files = []
        for category in categories:
            category_files = [file for file in system_service.config_files if file.get('category') == category]
            relevant_files.extend(category_files)
        print(f"Relevant files: {relevant_files}")
        await sio.emit('context_files', {'files': relevant_files})
        # index_path = system_service.config_db.get_index_path()
        # colbert_service = ColbertService(index_path, uid)
        # query_results = colbert_service.search_index(query)
        # for result in query_results:
        #     pprint.pprint(result['document_metadata'])
        #     pprint.pprint(result['rank'])
    except HTTPException as e:
        error_message = f"Unauthorized access: {str(e)}"
        await sio.emit('error', {'message': error_message}, room=sid)
        return

def get_db():
    try:
        mongo_client = MongoDbClient.get_instance('paxxium')
        return mongo_client.db
    except Exception as e:
        raise Exception(f"Database connection failed: {str(e)}")


def setup_system_agent_handlers(sio):
    @sio.on('system_agent')
    async def system_agent_handler(sid, data):
        await handle_system_agent(sio, sid, data)