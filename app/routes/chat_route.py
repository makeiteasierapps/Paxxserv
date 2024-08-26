import json
from dotenv import load_dotenv
from flask import Blueprint, request, g, jsonify
from flask_cors import CORS
from app.services.ChatService import ChatService
from app.services.FirebaseStoreageService import FirebaseStorageService as firebase_storage
from app.services.MongoDbClient import MongoDbClient

load_dotenv()

chat_bp = Blueprint('chat', __name__)
cors = CORS(resources={r"/*": {
    "origins": ["https://paxxiumv1.web.app", "http://localhost:3000"],
    "allow_headers": ["Content-Type", "Accept", "dbName", "uid"],
    "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE", "PATCH"],
}})

@chat_bp.before_request
def initialize_services():
    if request.method == 'OPTIONS':
        return ("", 204)
    
    db_name = request.headers.get('dbName')
    if not db_name:
        return jsonify({"error": "dbName is required in the headers"}), 400
    g.uid = request.headers.get('uid')
    g.mongo_client = MongoDbClient(db_name)
    db = g.mongo_client.connect()
    g.chat_service = ChatService(db)
        

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
def handle_messages(subpath):
    if request.method == 'DELETE' and subpath == '':
        chat_id = request.json.get('chatId')
        g.chat_service.delete_all_messages(chat_id)
        return 'Memory Cleared', 200
    
    if subpath == 'utils':
        uid = request.headers.get('userId')
        file = request.files['image']
        file_url = firebase_storage.upload_file(file, uid, 'gpt-vision')
        return (json.dumps({'fileUrl': file_url}), 200)
    