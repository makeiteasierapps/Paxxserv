from flask_socketio import join_room
from flask import request, jsonify
import json
from app import socketio
from app.services.ChatService import ChatService
from app.services.ProfileService import ProfileService
from app.agents.BossAgent import BossAgent
from app.agents.AnthropicClient import AnthropicClient
from app.agents.OpenAiClient import OpenAiClient
from app.services.MongoDbClient import MongoDbClient
from app.services.ExtractionService import ExtractionService
from app.services.KnowledgeBaseService import KnowledgeBaseService

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('join_room')
def handle_join_room(data):
    room = data['chatId']
    join_room(room)
    print(f"Client {request.sid} joined room {room}")

def initialize_services(db_name, uid):
    mongo_client = MongoDbClient(db_name)
    db = mongo_client.connect()
    chat_service = ChatService(db)
    profile_service = ProfileService(db, uid)
    kb_service = KnowledgeBaseService(db, uid)
    extraction_service = ExtractionService(db, uid)
    return db, chat_service, profile_service, kb_service, extraction_service

def create_boss_agent(chat_settings, db, uid, profile_service):
    if not chat_settings:
        return None, None

    chat_constants = chat_settings.get('chat_constants')
    use_profile_data = chat_settings.get('use_profile_data', False)
    model = chat_settings.get('agent_model')
    system_prompt = chat_settings.get('system_prompt')
    user_analysis = profile_service.get_user_analysis(uid) if use_profile_data else None

    if model.startswith('claude'):
        ai_client = AnthropicClient(db, uid)
    else:
        ai_client = OpenAiClient(db, uid)

    boss_agent = BossAgent(
        ai_client=ai_client,
        model=model,
        system_prompt=system_prompt,
        chat_constants=chat_constants,
        user_analysis=user_analysis
    )

    return boss_agent, system_prompt
    
def handle_extraction(urls, extraction_service, kb_id, kb_service, boss_agent, system_prompt):
    extracted_docs = []
    for url in urls:
        for result in extraction_service.extract_from_url(url, kb_id, 'scrape', kb_service):
            result_dict = json.loads(result)
            if result_dict['status'] == 'completed':
                extracted_docs.append(result_dict['content'])
            elif result_dict['status'] == 'error':
                print(f"Error extracting from URL: {result_dict['message']}")
    if extracted_docs:
        extracted_docs_response = extraction_service.parse_extraction_response(extracted_docs)
        return boss_agent.prepare_url_content_for_ai(extracted_docs_response, system_prompt)
    return None

@socketio.on('chat_request')
def handle_chat_message(data):
    urls = data.get('urls', [])
    uid = data.get('uid')
    save_to_db = data.get('saveToDb', False)
    kb_id = data.get('kbId', None)
    chat_settings = data.get('chatSettings', None)
    db_name = data.get('dbName')
    user_message = data['userMessage']['content']
    chat_id = data['chatId']
    image_url = data.get('imageUrl', None)
    system_message = None

    if save_to_db and not db_name:
        return jsonify({"error": "dbName is required in the headers"}), 400

    db, chat_service, profile_service, kb_service, extraction_service = initialize_services(db_name, uid)
    boss_agent, system_prompt = create_boss_agent(chat_settings, db, uid, profile_service)

    if save_to_db:
        chat_service.create_message(chat_id, 'user', user_message)
        def save_agent_message(chat_id, message):
            chat_service.create_message(chat_id, 'agent', message)
    else:
        save_agent_message = None

    if kb_id:
        query_pipeline = boss_agent.create_vector_pipeline(user_message, kb_id)
        results = chat_service.query_snapshots(query_pipeline)
        system_message = boss_agent.prepare_vector_response(results, system_prompt)

    if urls:
        system_message = handle_extraction(urls, extraction_service, kb_id, kb_service, boss_agent, system_prompt)

    boss_agent.process_message(data['chatHistory'], chat_id, user_message, system_message, save_agent_message, image_url)