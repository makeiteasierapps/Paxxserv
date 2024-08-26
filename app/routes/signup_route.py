from dotenv import load_dotenv
from flask import Blueprint, request, g
from flask_cors import CORS
from app.services.UserService import UserService
from app.services.MongoDbClient import MongoDbClient

load_dotenv()

signup_bp = Blueprint('signup_bp', __name__)
cors = CORS(resources={r"/*": {
    "origins": ["https://paxxiumv1.web.app", "http://localhost:3000"],
    "allow_headers": ["Content-Type", "Accept", "dbName", "uid"],
    "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE", "PATCH"],
}})

@signup_bp.before_request
def initialize_services():
    if request.method == "OPTIONS":
        return ("", 204)
    db_name = request.headers.get('dbName')
    if not db_name:
        return ('Database name is required', 400)
    g.mongo_client = MongoDbClient(db_name)
    db = g.mongo_client.connect()
    g.user_service = UserService(db)

@signup_bp.route('/signup', methods=['POST'])
def signup():
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
      
        g.user_service.update_user(uid, updates)

        return ({'message': 'User added successfully'}, 200)

