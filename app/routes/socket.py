from flask_socketio import join_room
from flask import request, jsonify
from app import socketio
from app.services.ChatService import ChatService
from app.services.ProfileService import ProfileService
from app.agents.BossAgent import BossAgent
from app.services.MongoDbClient import MongoDbClient


@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('join_room')
def handle_join_room(data):
    room = data['chatId']
    join_room(room)
    print(f"Client {request.sid} joined room {room}")

@socketio.on('chat_request')
def handle_chat_message(data):
    uid = data.get('userId')
    save_to_db = data.get('saveToDb', False)
    use_kb = data.get('useKb', False)
    chat_settings = data.get('chatSettings', None)
    db_name = data.get('dbName')
    system_prompt = None
    user_message = data['userMessage']['content']
    chat_id = data['chatId']
    image_url = data.get('imageUrl', None)
    system_message = None
    
    if save_to_db and not db_name:
        return jsonify({"error": "dbName is required in the headers"}), 400
    
    if save_to_db:
        mongo_client = MongoDbClient(db_name)
        db = mongo_client.connect()
        chat_service = ChatService(db)
        profile_service = ProfileService(db)

        chat_service.create_message(chat_id, 'user', user_message)
        def save_agent_message(chat_id, message):
            chat_service.create_message(chat_id, 'agent', message)
        
        if chat_settings:
            chat_constants = chat_settings.get('chat_constants')
            use_profile_data = chat_settings.get('use_profile_data', False)
            model = chat_settings.get('agent_model', None)
            system_prompt = chat_settings.get('system_prompt')
            user_analysis = None
            if use_profile_data:
                user_analysis = profile_service.get_user_analysis(uid)
            boss_agent = BossAgent(model=model, chat_constants=chat_constants, system_prompt=system_prompt, user_analysis=user_analysis, db=db, uid=uid)
        else: 
            boss_agent = BossAgent(model='gpt-4o', db=db, uid=uid)  
        if use_kb:
                query_pipeline = boss_agent.create_vector_pipeline(user_message, data['kbId'])
                results = chat_service.query_snapshots(query_pipeline)
                system_message = boss_agent.prepare_vector_response(results, system_prompt)
    else:
        mongo_client = MongoDbClient(db_name)
        db = mongo_client.connect()
        chat_service = ChatService(db)
        boss_agent = BossAgent(model='gpt-4o', db=db, uid=uid)
        if use_kb:
            query_pipeline = boss_agent.create_vector_pipeline(user_message, data['kbId'])
            results = chat_service.query_snapshots(query_pipeline)
            system_message = boss_agent.prepare_vector_response(results, system_prompt)
         
    
    boss_agent.process_message(data['chatHistory'], chat_id, user_message, system_message, save_agent_message if save_to_db else None, image_url)