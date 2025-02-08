import logging
from app.services.ChatService import ChatService
from app.services.InsightService import InsightService
from app.agents.QuestionGenerator import QuestionGenerator
from app.agents.BossAgent import BossAgent, BossAgentConfig
from app.agents.OpenAiClient import OpenAiClient
from app.services.MongoDbClient import MongoDbClient
tools = [{
    "type": "function",
    "function": {
        "name": "extract_user_data",
        "description": "Used when the user provides information about themselves",
        "parameters": {
            "type": "object", 
            "properties": {
            "user_info": {
                "type": "string", 
                "description": "The user's information"}
        }, 
        "required": ["user_info"],
        }
    }
}
]

def get_db():
    try:
        mongo_client = MongoDbClient.get_instance('paxxium')
        return mongo_client.db
    except Exception as e:
        raise Exception(f"Database connection failed: {str(e)}")
    
def create_insight_agent(sio, db, uid):
    question_generator = QuestionGenerator(db, uid)
    insight_service = InsightService(db, sio, uid, question_generator)
    function_map = {
        "extract_user_data": insight_service.extract_user_data
    }
    ai_client = OpenAiClient(db, uid)
    config = BossAgentConfig(ai_client, sio, event_name='insight_chat_response', tools=tools, tool_choice='required', function_map=function_map)
    insight_agent = BossAgent(config)
    return insight_agent

def validate_chat_settings(data):
    chat_settings = data.get('selectedChat')
    if not chat_settings:
        raise ValueError("Chat settings are missing")
    return chat_settings

async def run_insight_agent(sio, sid, data):
    try:
        # Get and validate settings
        chat_object = validate_chat_settings(data)
        uid, chat_id = chat_object.get('uid'), chat_object.get('chatId')
        user_message = chat_object.get('messages', [])[-1] if chat_object.get('messages') else None

        db = get_db()
        chat_service = ChatService(db, chat_type='insight')

        await chat_service.create_message(chat_id, 'user', user_message.get('content'))

        # Process message with system agent
        insight_agent = create_insight_agent(sio, db, uid)
        await insight_agent.process_message(
            chat_object['messages'], 
            chat_id, 
            # lambda cid, msg: chat_service.create_message(cid, 'agent', msg)
        )

    except Exception as e:
        logging.error('Error in run_insight_agent: %s', str(e))
        await sio.emit('error', {'message': f"Error processing request: {str(e)}"}, room=sid)

def setup_insight_agent_handlers(sio):
    @sio.on('insight_chat_response')
    async def get_agent_response_handler(sid, data):
        await run_insight_agent(sio, sid, data)
