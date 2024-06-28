from flask import Blueprint, request, Response
import os
import json
from app.services.ChatService import ChatService
from app.agents.BossAgent import BossAgent
from dotenv import load_dotenv

load_dotenv()

chat_bp = Blueprint('chat', __name__)

headers = {"Access-Control-Allow-Origin": "*"}

@chat_bp.route('/chat', methods=['OPTIONS'])
@chat_bp.route('/messages', methods=['OPTIONS'])
def cors_preflight_response():
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS, DELETE, PUT, PATCH",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, Project-ID, X-API-Key",
        "Access-Control-Max-Age": "3600",
    }
    return ("", 204, cors_headers)

def check_api_key(request):
    api_key = request.headers.get('X-API-Key')
    print(api_key)
    print(os.getenv('API_KEY'))
    if api_key == os.getenv('API_KEY'):
        return True
    else:
        return False

@chat_bp.route('/chat', methods=['GET'])
def handle_fetch_chats():
    if not check_api_key(request):
        return {'message': 'Unauthorized'}, 401, headers
    user_id = request.headers.get('userId')
    return ChatService().get_all_chats(user_id), 200, headers

@chat_bp.route('/chat', methods=['POST'])
def handle_create_chat():
    if not check_api_key(request):
        return {'message': 'Unauthorized'}, 401, headers
    data = request.get_json()
    chat_service = ChatService()
    chat_id = chat_service.create_chat_in_db(data['userId'], data['chatName'], data['model'])
    return {
        'chatId': chat_id,
        'chat_name': data['chatName'],
        'model': data['model'],
        'userId': data['userId'],
    }, 200, headers

@chat_bp.route('/chat', methods=['DELETE'])
def handle_delete_chat():
    if not check_api_key(request):
        return {'message': 'Unauthorized'}, 401, headers
    chat_id = request.get_json()['chatId']
    ChatService().delete_chat(chat_id)
    return 'Conversation deleted', 200, headers

@chat_bp.route('/messages', methods=['POST'])
def handle_post_message():
    if not check_api_key(request):
        return {'message': 'Unauthorized'}, 401, headers
    data = request.json
    save_to_db = data.get('saveToDb', True)
    create_vector_pipeline = data.get('createVectorPipeline', False)
    boss_agent = BossAgent()
    chat_service = ChatService(db_name=data['dbName'])
    user_message = data['userMessage']['content']

    if create_vector_pipeline:
        query_pipeline = boss_agent.create_vector_pipeline(user_message, data['projectId'])
        results = chat_service.query_snapshots(query_pipeline)
        print(results)
        system_message = boss_agent.prepare_vector_response(results)
        
    complete_message = ''
    response_generator = boss_agent.process_message(data['chatId'], data['chatHistory'], user_message, system_message)

    def compile_and_stream():
        nonlocal complete_message
        for response in response_generator:
            complete_message += response['content']
            yield json.dumps(response) + '\n'

    response = Response(compile_and_stream(), mimetype='application/json')
    
    if save_to_db:
        chat_service.create_message(data['chatId'], 'user', user_message)
        response.call_on_close(lambda: chat_service.create_message(data['chatId'], 'agent', complete_message))
    
    return response

@chat_bp.route('/messages', methods=['DELETE'])
def handle_delete_all_messages():
    if not check_api_key(request):
        return {'message': 'Unauthorized'}, 401, headers
    chat_id = request.json.get('chatId')
    ChatService().delete_all_messages(chat_id)
    return 'Memory Cleared', 200, headers