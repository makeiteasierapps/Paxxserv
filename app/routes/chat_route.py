import json
from dotenv import load_dotenv
from flask import Blueprint, request, Response, g, jsonify
from flask_socketio import join_room
from app import socketio
from app.services.ChatService import ChatService
from app.services.UserService import UserService
from app.agents.BossAgent import BossAgent
from app.services.MongoDbClient import MongoDbClient

load_dotenv()

chat_bp = Blueprint('chat', __name__)

@chat_bp.before_request
def initialize_services():
    if request.method == 'OPTIONS':
        return ("", 204)
    
    db_name = request.headers.get('dbName')
    if not db_name:
        return jsonify({"error": "dbName is required in the headers"}), 400
    g.uid = request.headers.get('userId')
    g.mongo_client = MongoDbClient(db_name)
    db = g.mongo_client.connect()
    g.chat_service = ChatService(db)
    g.user_service = UserService(db)
        
@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@chat_bp.route('/socket.io/', methods=['OPTIONS'])
def handle_socketio_options():
    response = Response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@chat_bp.route('/chat', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'])
@chat_bp.route('/chat/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'])
def chat(subpath):
    if request.method == 'GET' and subpath == '':
        return g.chat_service.get_all_chats(g.uid), 200
    
    if request.method == 'POST' and subpath == '':
        data = request.get_json()
        
        chat_id = g.chat_service.create_chat_in_db(
        data['userId'], 
        data['chatName'], 
        data['agentModel'], 
        system_prompt=data.get('systemPrompt'), 
        chat_constants=data.get('chatConstants'), 
        use_profile_data=data.get('useProfileData')
    )
        return {
            'chatId': chat_id,
            'chat_name': data['chatName'],
            'agentModel': data['agentModel'],
            'userId': data['userId'],
            'systemPrompt': data.get('systemPrompt'),
            'chatConstants': data.get('chatConstants'),
            'useProfileData': data.get('useProfileData'),
            'is_open': True
        }, 200

    if request.method == 'DELETE' and subpath == '':
        chat_id = request.get_json()['chatId']
        g.chat_service.delete_chat(chat_id)
        return 'Conversation deleted', 200
    
    if subpath == 'update_visibility':
        data = request.get_json()
        chat_id = data['chatId']
        is_open = data['is_open']
        g.chat_service.update_visibility(chat_id, is_open)
        return ('Chat visibility updated', 200)

    if subpath == 'update_settings':
        data = request.get_json()
        use_profile_data = data.get('use_profile_data')
        chat_name = data.get('chat_name')
        chat_id = data.get('chatId')
        agent_model = data.get('agent_model')
        system_prompt = data.get('system_prompt')
        chat_constants = data.get('chat_constants')
        g.chat_service.update_settings(chat_id, chat_name, agent_model, system_prompt, chat_constants, use_profile_data)

        return ('Chat settings updated', 200)

@chat_bp.route('/messages', defaults={'subpath': ''}, methods=['DELETE', 'POST'])
@chat_bp.route('/messages/<path:subpath>', methods=['DELETE', 'POST'])
def handle_delete_all_messages(subpath):
    if request.method == 'DELETE' and subpath == '':
        chat_id = request.json.get('chatId')
        g.chat_service.delete_all_messages(chat_id)
        return 'Memory Cleared', 200
    
    if subpath == 'utils':
        uid = request.headers.get('userId')
        file = request.files['image']
        file_url = g.user_service.upload_file_to_firebase_storage(file, uid)
        return (json.dumps({'fileUrl': file_url}), 200)
    
# SOCKET EVENTS
@socketio.on('join_room')
def handle_join_room(data):
    room = data['chatId']
    join_room(room)
    print(f"Client {request.sid} joined room {room}")

@socketio.on('chat_request')
def handle_chat_message(data):
    uid = data.get('userId')
    save_to_db = data.get('saveToDb', False)
    create_vector_pipeline = data.get('createVectorPipeline', False)
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
        user_service = UserService(db)
        openai_key = user_service.get_keys(uid)

        chat_service.create_message(chat_id, 'user', user_message)
        def save_agent_message(chat_id, message):
            chat_service.create_message(chat_id, 'agent', message)
        
        if chat_settings:
            chat_constants = chat_settings.get('chatConstants')
            use_profile_data = chat_settings.get('useProfileData', None)
            model = chat_settings.get('agentModel', None)
            system_prompt = chat_settings.get('systemPrompt')
            user_analysis = None
            if use_profile_data:
                user_analysis = user_service.get_user_analysis(uid)
            boss_agent = BossAgent(openai_key=openai_key, model=model, chat_constants=chat_constants, system_prompt=system_prompt, user_analysis=user_analysis)
        else: 
            boss_agent = BossAgent(openai_key=openai_key, model='gpt-4o')  
        if create_vector_pipeline:
                query_pipeline = boss_agent.create_vector_pipeline(user_message, data['projectId'])
                results = chat_service.query_snapshots(query_pipeline)
                system_message = boss_agent.prepare_vector_response(results, system_prompt)
    else:
        boss_agent = BossAgent(openai_key=openai_key, model='gpt-4o')
        mongo_client = MongoDbClient(db_name)
        db = mongo_client.connect()
        chat_service = ChatService(db)
        if create_vector_pipeline:
            query_pipeline = boss_agent.create_vector_pipeline(user_message, data['projectId'])
            results = chat_service.query_snapshots(query_pipeline)
            system_message = boss_agent.prepare_vector_response(results, system_prompt)
         
    
    boss_agent.process_message(data['chatHistory'], chat_id, user_message, system_message, save_agent_message if save_to_db else None, image_url)
