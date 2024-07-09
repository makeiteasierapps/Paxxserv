import os
import json
from flask import Blueprint, request, jsonify
from dotenv import load_dotenv
from firebase_admin import credentials, initialize_app
from app.services.FirebaseService import FirebaseService
from app.services.UserService import UserService
from app.agents.BossAgent import BossAgent

load_dotenv()

profile_bp = Blueprint('profile_bp', __name__)

cred = credentials.Certificate(os.getenv('FIREBASE_ADMIN_SDK'))

try:
    initialize_app(cred, {
        'projectId': 'paxxiumv1',
        'storageBucket': 'paxxiumv1.appspot.com'
    })
except ValueError:
    pass

firebase_service = FirebaseService()
user_service = UserService(db_name='paxxium')

@profile_bp.route('/profile', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@profile_bp.route('/profile/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def profile(subpath):
    if request.method == "OPTIONS":
        return "", 204

    uid = request.headers.get('uid')

    if request.method == 'GET' and subpath == '':
        user_profile = user_service.get_profile(uid)
        return jsonify(user_profile), 200

    if subpath == 'answers':
        if request.method == 'POST':
            data = request.get_json()
            user_service.update_profile_answers(uid, data)
            return jsonify({'response': 'Profile questions/answers updated successfully'}), 200
        profile_data = user_service.load_profile_answers(uid)
        return jsonify(profile_data), 200

    if subpath == 'user':
        data = request.get_json()
        user_service.update_user_profile(uid, data)
        return jsonify({'response': 'User profile updated successfully'}), 200
    
    if subpath == 'analyze':
        encrypted_openai_key = user_service.get_keys(uid)
        openai_key = user_service.decrypt(encrypted_openai_key)
        profile_agent = BossAgent(openai_key=openai_key, model='gpt-4o')
        prompt = user_service.prepare_analysis_prompt(uid)
        response = profile_agent.pass_to_profile_agent(prompt)
        analysis_obj = json.loads(response)
        user_service.update_user_profile(uid, analysis_obj.copy())
        return jsonify(analysis_obj), 200

    if subpath in ('update_avatar', 'profile/update_avatar'):
        file = request.files['avatar']
        avatar_url = user_service.upload_profile_image_to_firebase_storage(file, uid)
        return jsonify({'avatar_url': avatar_url}), 200

    return 'Not Found', 404

    
    