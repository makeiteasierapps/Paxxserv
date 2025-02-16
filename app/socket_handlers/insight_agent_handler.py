import logging
from app.services.InsightService import InsightService
from app.agents.QuestionGenerator import QuestionGenerator
from app.agents.BossAgent import BossAgent, BossAgentConfig
from app.agents.OpenAiClient import OpenAiClient


# tools = [{
#     "type": "function",
#     "function": {
#         "name": "extract_user_data",
#         "description": "Used when the user provides information about themselves",
#         "parameters": {
#             "type": "object", 
#             "properties": {
#             "user_info": {
#                 "type": "string", 
#                 "description": "The user's information"}
#         }, 
#         "required": ["user_info"],
#         }
#     }
# }
# ]

CATEGORIES = [
    "basic_demographics",

    "cultural_influences",
    "personal_background",
    "interests_and_hobbies",
    "social_relationships",
    "emotional_landscape",
    "self_perception",
    "coping_mechanisms",
    "life_philosophy",
    "pivotal_past_experiences",
    "personal_storytelling",
    "daily_routine",
    "work_life_balance",
    "lifestyle_preferences",
    "goals_and_aspirations",
    "values_and_beliefs",
    "behavior_patterns",
    "challenges_and_pain_points",
    "mindset_and_attitude",
    "emotional_intelligence",
    "personal_growth",
    "behavior_patterns",
    "future_social_relationship_goals",
    "future_identity",
    "personal_growth",
    "future_identity",
]

SUBCATEGORIES = [
    "age_range",
    "gender_identity",
    "location",
    "education_level",
    "occupation",
    "regular_hobbies",
    "current_interests",
    "artistic_inclinations",
    "learning_interests",
    "passions",
    "hobbies_shared_with_others",
    "relationship_history",
    "current_dynamics",
    "interaction_patterns",
    "mood_patterns",
    "emotional_triggers",
    "strengths",
    "weaknesses",
    "life_meaning",
    "narratives_about_self",
    "life_lessons",
    "work",
    "leisure",
    "exercise",
    "spiritual_practices",
    "spiritual_beliefs",
       
]

tools = [{
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
                                        "enum": CATEGORIES,
                                        "description": "The category this answer belongs to. If none of the existing categories match, return a new suggested category."
                                    },
                                    "subcategory": {
                                        "type": "string",
                                        "enum": SUBCATEGORIES,
                                        "description": "A more specific subcategory within the chosen category. If none of the existing subcategories match, return a new suggested subcategory."
                                    },
                                    "is_new_category": {
                                        "type": "boolean",
                                        "description": "True if this is a newly suggested category."
                                    },
                                    "is_new_subcategory": {
                                        "type": "boolean",
                                        "description": "True if this is a newly suggested subcategory."
                                    }
                                },
                                "required": ["name", "subcategory", "is_new_category", "is_new_subcategory"],
                                "description": "The category and subcategory that best describes this answer."
                            },
                            "follow_up_question": {
                                "type": "string",
                                "description": "A follow-up question generated to encourage deeper exploration of this topic."
                            }
                        },
                        "required": ["question", "answer", "category", "subcategory", "follow_up_question"]
                    },
                    "description": "A list of user-provided information entries with their associated categories, subcategories, and follow-up questions."
                }
            },
            "required": ["user_entries"]
        }
    }
}]

    
def create_insight_agent(sio, db, uid, insight_service):
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

async def run_insight_agent(sio, sid, data, mongo_client):
    try:
        # Get and validate settings
        chat_object = validate_chat_settings(data)
        uid = chat_object.get('uid')
        user_message = chat_object.get('messages', [])[-1] if chat_object.get('messages') else None

        db = mongo_client.db
        question_generator = QuestionGenerator(db, uid)
        insight_service = InsightService(db, sio, uid, question_generator)

        # Process message with system agent
        insight_agent = create_insight_agent(sio, db, uid, insight_service)
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
