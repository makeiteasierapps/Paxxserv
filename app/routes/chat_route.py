from flask import Blueprint, request, Response, g
from flask_socketio import join_room
import json
from app import socketio
from app.services.ChatService import ChatService
from app.services.UserService import UserService
from app.agents.BossAgent import BossAgent
from dotenv import load_dotenv

load_dotenv()

chat_bp = Blueprint('chat', __name__)

@chat_bp.before_request
def initialize_services():
    db_name = request.headers.get('dbName', 'paxxium')
    g.chat_service = ChatService(db_name=db_name)
    g.user_service = UserService(db_name=db_name)

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@chat_bp.route('/socket.io/', methods=['OPTIONS'])
def handle_socketio_options():
    response = Response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response


@chat_bp.route('/messages', methods=['OPTIONS'])
def handle_messages_options():
    if request.method == 'OPTIONS':
        return ("", 204)
@chat_bp.route('/chat', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'])
@chat_bp.route('/chat/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'])
def chat(subpath):
    if request.method == 'OPTIONS':
        return ("", 204)

    if request.method == 'GET' and subpath == '':
        user_id = request.headers.get('userId')
        return g.chat_service.get_all_chats(user_id), 200
    
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

@socketio.on('join_room')
def handle_join_room(data):
    room = data['chatId']
    join_room(room)
    print(f"Client {request.sid} joined room {room}")

@socketio.on('chat_request')
def handle_chat_message(data):
    uid = data.get('userId')
    system_prompt = None
    chat_settings = data.get('chatSettings', None)
    if chat_settings:
        chat_constants = chat_settings.get('chatConstants')
        use_profile_data = chat_settings.get('useProfileData', None)
        model = chat_settings.get('agentModel', None)
        print('received model', model)
        system_prompt = chat_settings.get('systemPrompt')
        user_analysis = None
        if use_profile_data:
            user_analysis = g.user_service.get_user_analysis(uid)
        boss_agent = BossAgent(model=model, chat_constants=chat_constants, system_prompt=system_prompt, user_analysis=user_analysis)
    else:
        boss_agent = BossAgent(model='gpt-4o')
    
    chat_service_with_db = ChatService(db_name=data['dbName'])  
    user_message = data['userMessage']['content']
    chat_id = data['chatId']

    create_vector_pipeline = data.get('createVectorPipeline', False)
    if create_vector_pipeline:
        query_pipeline = boss_agent.create_vector_pipeline(user_message, data['projectId'])
        results = chat_service_with_db.query_snapshots(query_pipeline)
        system_message = boss_agent.prepare_vector_response(results, system_prompt)
    else:
        system_message = None

    save_to_db = data.get('saveToDb', True)
    if save_to_db:
        g.chat_service.create_message(chat_id, 'user', user_message)

    def save_agent_message(chat_id, message):
        g.chat_service.create_message(chat_id, 'agent', message)

    image_url = data.get('imageUrl', None)
    boss_agent.process_message(data['chatHistory'], chat_id, user_message, system_message, save_agent_message if save_to_db else None, image_url)

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