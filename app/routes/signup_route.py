import os
from dotenv import load_dotenv
from flask import Blueprint, request
from app.services.FirebaseService import FirebaseService
from app.services.UserService import UserService
from firebase_admin import credentials, initialize_app

load_dotenv()

signup_bp = Blueprint('signup_bp', __name__)

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

@signup_bp.route('/signup', methods=['POST'])
def signup():

    if request.method == "OPTIONS":
        return ("", 204)
    
    if request.method == 'POST':
        req_data = request.get_json()
        username = req_data.get('username')
        uid = req_data.get('uid')
        openai_api_key = req_data.get('openAiApiKey')
        authorized = req_data.get('authorized')

        updates = {   
            'username': username,
            'open_key': openai_api_key,
            'authorized': authorized}
      
        user_service.update_user_profile(uid, updates)

        return ({'message': 'User added successfully'}, 200)

