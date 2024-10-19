from app.services.MongoDbClient import MongoDbClient

async def handle_system_agent(sio, sid, data):
    print(data)

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