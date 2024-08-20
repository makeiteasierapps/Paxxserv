import os
from pymongo.errors import PyMongoError
from dotenv import load_dotenv
from flask import Blueprint, request, jsonify, g, current_app
from app.services.MongoDbClient import MongoDbClient

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
        try:
            uid = request.json.get('uid')
            user_doc = g.db['users'].find_one({'_id': uid})  
            auth_status = user_doc.get('authorized', False)
            return jsonify({'auth_status': auth_status})
        except PyMongoError as e:
            current_app.logger.error(f"Database error: {str(e)}")
            return jsonify({'error': 'Database error occurred'}), 500
        except Exception as e:
            current_app.logger.error(f"Unexpected error: {str(e)}")
            return jsonify({'error': 'An unexpected error occurred'}), 500
    
    if request.method == 'GET':
        try:
            current_app.logger.info("Fetching Firebase configuration")
            config = {
               "apiKey": os.getenv('FIREBASE_API_KEY'),
               "authDomain": os.getenv('FIREBASE_AUTH_DOMAIN'),
               "projectId": os.getenv('FIREBASE_PROJECT_ID'),
               "messagingSenderId": os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
               "appId": os.getenv('FIREBASE_APP_ID'),
            }
            
            # Check if all required configuration values are present
            missing_keys = [key for key, value in config.items() if value is None]
            if missing_keys:
                current_app.logger.error(f"Missing Firebase configuration keys: {', '.join(missing_keys)}")
                return jsonify({'error': 'Incomplete Firebase configuration'}), 500
            
            current_app.logger.info("Firebase configuration fetched successfully")
            return jsonify(config)
        except Exception as e:
            current_app.logger.error(f"Error fetching Firebase configuration: {str(e)}")
            return jsonify({'error': 'An error occurred while fetching the configuration'}), 500