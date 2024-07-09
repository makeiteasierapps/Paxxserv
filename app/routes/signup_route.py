from dotenv import load_dotenv
from flask import Blueprint, request, g
from app.services.UserService import UserService

load_dotenv()

signup_bp = Blueprint('signup_bp', __name__)

@signup_bp.before_request
def initialize_services():
    g.user_service = UserService(db_name='paxxium')

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
      
        g.user_service.update_user_profile(uid, updates)

        return ({'message': 'User added successfully'}, 200)

