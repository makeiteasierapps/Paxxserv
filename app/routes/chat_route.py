from flask import Blueprint, request, Response
from flask_socketio import join_room
from app import socketio
from app.services.ChatService import ChatService
from app.agents.BossAgent import BossAgent
from dotenv import load_dotenv

load_dotenv()

chat_bp = Blueprint('chat', __name__)

headers = {"Access-Control-Allow-Origin": "*"}

chat_service = ChatService('paxxium')

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
@chat_bp.route('/chat', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@chat_bp.route('/chat/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def chat(subpath):
    if request.method == 'OPTIONS':
        return ("", 204)

    if request.method == 'GET' and subpath == '':
        user_id = request.headers.get('userId')
        return chat_service.get_all_chats(user_id), 200, headers
    
    if request.method == 'POST' and subpath == '':
        data = request.get_json()
        chat_id = chat_service.create_chat_in_db(
        data['userId'], 
        data['chatName'], 
        data['model'], 
        system_prompt=data.get('systemPrompt'), 
        chat_constants=data.get('chatConstants'), 
        use_profile_data=data.get('useProfileData')
    )
        return {
            'chatId': chat_id,
            'chat_name': data['chatName'],
            'model': data['model'],
            'userId': data['userId'],
            'systemPrompt': data.get('systemPrompt'),
            'chatConstants': data.get('chatConstants'),
            'useProfileData': data.get('useProfileData')
        }, 200, headers

    if request.method == 'DELETE' and subpath == '':
        chat_id = request.get_json()['chatId']
        chat_service.delete_chat(chat_id)
        return 'Conversation deleted', 200, headers
    
    if subpath == 'update_visibility':
        data = request.get_json()
        chat_id = data['chatId']
        is_open = data['is_open']
        chat_service.update_visibility(chat_id, is_open)
        return ('Chat visibility updated', 200, headers)

    if subpath == 'update_settings':
        data = request.get_json()
        use_profile_data = data.get('use_profile_data')
        chat_name = data.get('chat_name')
        chat_id = data.get('chatId')
        agent_model = data.get('agent_model')
        system_prompt = data.get('system_prompt')
        chat_constants = data.get('chat_constants')
        chat_service.update_settings(chat_id, chat_name, agent_model, system_prompt, chat_constants, use_profile_data)

        return ('Chat settings updated', 200, headers)

@socketio.on('join_room')
def handle_join_room(data):
    room = data['chatId']
    join_room(room)
    print(f"Client {request.sid} joined room {room}")

@socketio.on('chat_request')
def handle_chat_message(data):
    save_to_db = data.get('saveToDb', True)
    create_vector_pipeline = data.get('createVectorPipeline', False)
    boss_agent = BossAgent()
    chat_service_with_db = ChatService(db_name=data['dbName'])  
    user_message = data['userMessage']['content']
    chat_id = data['chatId']

    if create_vector_pipeline:
        query_pipeline = boss_agent.create_vector_pipeline(user_message, data['projectId'])
        results = chat_service_with_db.query_snapshots(query_pipeline)
        system_message = boss_agent.prepare_vector_response(results)
    else:
        system_message = None

    if save_to_db:
        chat_service.create_message(chat_id, 'user', user_message)

    boss_agent.process_message(data['chatHistory'], chat_id, user_message, system_message)

@chat_bp.route('/messages', methods=['DELETE'])
def handle_delete_all_messages():
    chat_id = request.json.get('chatId')
    chat_service.delete_all_messages(chat_id)
    return 'Memory Cleared', 200, headers