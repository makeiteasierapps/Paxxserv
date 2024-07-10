import os
import json
from flask import Blueprint, request, jsonify, g
from dotenv import load_dotenv
from app.services.UserService import UserService
from app.services.ProfileService import ProfileService
from app.agents.BossAgent import BossAgent
from app.services.MongoDbClient import MongoDbClient

load_dotenv()

profile_bp = Blueprint('profile_bp', __name__)

@profile_bp.before_request
@profile_bp.before_request
def initialize_services():
    if request.method == "OPTIONS":
        return "", 204
    db_name = request.headers.get('dbName', 'paxxium')
    # Create the MongoDbClient instance and store it in g
    g.mongo_client = MongoDbClient(db_name)
    db = g.mongo_client.connect()
    g.user_service = UserService(db)
    openai_key = g.user_service.get_keys(g.uid)
    g.openai_client = BossAgent.get_openai_client(api_key=openai_key)
    g.profile_service = ProfileService(db, g.openai_client)
    g.uid = request.headers.get('uid')

@profile_bp.after_request
def close_mongo_connection(response):
    if hasattr(g, 'mongo_client'):
        g.mongo_client.close()
    return response

@profile_bp.route('/profile', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@profile_bp.route('/profile/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def profile(subpath):
    if request.method == 'GET' and subpath == '':
        user_profile = g.user_service.get_profile(g.uid)
        return jsonify(user_profile), 200

    if subpath == 'answers':
        if request.method == 'POST':
            data = request.get_json()
            g.user_service.update_profile_answers(g.uid, data)
            return jsonify({'response': 'Profile questions/answers updated successfully'}), 200
        profile_data = g.user_service.load_profile_answers(g.uid)
        return jsonify(profile_data), 200

    if subpath == 'user':
        data = request.get_json()
        g.user_service.update_user_profile(g.uid, data)
        return jsonify({'response': 'User profile updated successfully'}), 200
    
    if subpath == 'analyze':
        prompt = g.user_service.prepare_analysis_prompt(g.uid)
        response = g.profile_service.pass_to_profile_agent(prompt)
        analysis_obj = json.loads(response)
        g.user_service.update_user_profile(g.uid, analysis_obj.copy())
        return jsonify(analysis_obj), 200

    if subpath in ('update_avatar', 'profile/update_avatar'):
        file = request.files['avatar']
        avatar_url = g.user_service.upload_profile_image_to_firebase_storage(file, g.uid)
        return jsonify({'avatar_url': avatar_url}), 200

    return 'Not Found', 404

    
    