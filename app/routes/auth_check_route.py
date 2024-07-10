import os
from flask import Blueprint, request, jsonify, g
from app.services.MongoDbClient import MongoDbClient
from dotenv import load_dotenv

load_dotenv()

auth_check_bp = Blueprint('auth_check', __name__)

@auth_check_bp.before_request
def initialize_services():
    if request.method == 'OPTIONS':
        return ('', 204)
    if request.method == 'GET':
        return
    db_name = request.headers.get('dbName')
    if not db_name:
        return ('Database name is required', 400)
    g.mongo_client = MongoDbClient(db_name)
    db = g.mongo_client.connect()
    g.db = db

@auth_check_bp.route('/auth_check', methods=['POST', 'OPTIONS', 'GET'])
def auth_check():
    """
    Checks if admin has granted access to the user
    """
    
    if request.method == 'POST':
        uid = request.json.get('uid')
        user_doc = g.db['users'].find_one({'_id': uid})  
        auth_status = user_doc.get('authorized', False)
        return jsonify({'auth_status': auth_status})
    
    if request.method == 'GET':
        config = {
           "apiKey": os.getenv('FIREBASE_API_KEY'),
           "authDomain": os.getenv('FIREBASE_AUTH_DOMAIN'),
           "projectId": os.getenv('FIREBASE_PROJECT_ID'),
           "messagingSenderId": os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
           "appId": os.getenv('FIREBASE_APP_ID'),
       }
        return jsonify(config)