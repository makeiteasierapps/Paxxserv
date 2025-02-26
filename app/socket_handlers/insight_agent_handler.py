import logging
from app.services.InsightService import InsightService
from app.agents.BossAgent import BossAgent, BossAgentConfig
from app.agents.OpenAiClient import OpenAiClient


async def get_insight_tool():
    return [{
        "type": "function",
        "function": {
            "name": "extract_user_data",
            "description": "Used when the user provides information about themselves",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_entries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {
                                    "type": "string",
                                    "description": "The original question that prompted the user's response."
                                },
                                "answer": {
                                    "type": "string",
                                    "description": "A specific piece of user-provided information."
                                },
                                "category": {
                                    "type": "object",
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                            "description": "The category this answer belongs to."
                                        },
                                        "subcategory": {
                                            "type": "string",
                                            "description": "A subcategory that best describes this answer."
                                        },
                                    },
                                    "required": ["name", "subcategory"],
                                    "description": "The category and subcategory that best describes this answer."
                                },
                            },
                            "required": ["question", "answer", "category"]
                        },
                        "description": "A list of user-provided information entries with their associated categories, subcategories"
                    }
                },
                "required": ["user_entries"]
            }
        }
    }]


async def create_insight_agent(sio, db, uid, insight_service):
    function_map = {
        "extract_user_data": insight_service.extract_user_data
    }
    ai_client = OpenAiClient(db, uid)
    profile = await insight_service.get_user_profile_as_string()
    print(profile)
    system_message = f'''
    You have access to the user's known profile data. When extracting new insights, only include information that is not already present in the provided profile.

    If the user confirms previously known data, do not extract it again.

    If the user provides an updated version of an existing detail (e.g., new job, new city, changed preferences), classify it as an update.

    Maintain consistency in categorization.
    Here is the user's profile:
    {profile}
    '''
    tools = await get_insight_tool()
    config = BossAgentConfig(ai_client, sio, event_name='insight_chat_response', tools=tools, tool_choice='required', function_map=function_map, system_message=system_message, model='gpt-4o-mini')
    insight_agent = BossAgent(config)
    return insight_agent

def validate_chat_settings(data):
    chat_settings = data.get('selectedChat')
    if not chat_settings:
        raise ValueError("Chat settings are missing")
    return chat_settings

async def run_insight_agent(sio, sid, data, mongo_client):
    try:
        # Get and validate settings
        chat_object = validate_chat_settings(data)
        uid = chat_object.get('uid')
        user_message = chat_object.get('messages', [])[-1] if chat_object.get('messages') else None

        db = mongo_client.db
        insight_service = InsightService(db, sio, uid)

        # Process message with system agent
        insight_agent = await create_insight_agent(sio, db, uid, insight_service)
        await insight_service.create_message('user', user_message.get('content'))
        await insight_agent.process_message(
            chat_object['messages'], 
            'insight', 
            lambda cid, msg: insight_service.create_message('agent', msg)
        )

    except Exception as e:
        logging.error('Error in run_insight_agent: %s', str(e))
        await sio.emit('error', {'message': f"Error processing request: {str(e)}"}, room=sid)

def setup_insight_agent_handlers(sio, mongo_client):
    @sio.on('insight_chat_response')
    async def get_agent_response_handler(sid, data):
        await run_insight_agent(sio, sid, data, mongo_client)
