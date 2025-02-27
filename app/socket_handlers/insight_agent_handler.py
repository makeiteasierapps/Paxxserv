import logging
from app.agents.BossAgent import  BossAgentConfig
from app.agents.OpenAiClient import OpenAiClient
from app.agents.Insight.InsightAgent import InsightAgent

async def get_insight_tools():
    return [{
        "type": "function",
        "function": {
            "name": "extract_user_data",
            "description": "Used when the user provides information about themselves",
            "strict": True,
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
                                    "additionalProperties": False,
                                    "description": "The category and subcategory that best describes this answer."
                                },
                            },
                            "required": ["question", "answer", "category"],
                            "additionalProperties": False
                        },
                        "description": "A list of user-provided information entries with their associated categories, subcategories"
                    }
                },
                "required": ["user_entries"],
                "additionalProperties": False 
            }
        }
    }]

async def create_dspy_agent(sio, db, uid):
    ai_client = OpenAiClient(db, uid)

    system_message = f'''
    
    '''
    config = BossAgentConfig(ai_client, sio, event_name='insight_chat_response', system_message=system_message, model='gpt-4o')
    insight_agent = InsightAgent(config, db, uid)
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
        db = mongo_client.db
        insight_agent = await create_dspy_agent(sio, db, uid)

        await insight_agent.handle_user_input(chat_object.get('messages'))

    except Exception as e:
        logging.error('Error in run_insight_agent: %s', str(e))
        await sio.emit('error', {'message': f"Error processing request: {str(e)}"}, room=sid)

def setup_insight_agent_handlers(sio, mongo_client):
    @sio.on('insight_chat_response')
    async def get_agent_response_handler(sid, data):
        await run_insight_agent(sio, sid, data, mongo_client)
