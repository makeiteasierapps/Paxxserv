import os
import time
from flask_cors import CORS
from pymongo.errors import PyMongoError
from dotenv import load_dotenv
from flask import Blueprint, request, jsonify, g, current_app
from werkzeug.exceptions import HTTPException
from app.services.MongoDbClient import MongoDbClient

load_dotenv(override=True)

auth_check_bp = Blueprint('auth_check', __name__)
cors = CORS(resources={r"/*": {
    "origins": ["https://paxxiumv1.web.app", "http://localhost:3000"],
    "allow_headers": ["Content-Type", "Accept", "dbName", "uid"],
    "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE", "PATCH"],
}})

@auth_check_bp.before_request
def initialize_services():
    start_time = time.time()
    current_app.logger.info(f"Request method: {request.method}")
    current_app.logger.info(f"Received headers: {request.headers}")

    if request.method == 'OPTIONS':
        return jsonify({}), 200

    if request.method == 'GET':
        return

    db_name = request.headers.get('dbName')
    if not db_name:
        current_app.logger.warning('Database name is required but not provided.')
        return jsonify({'error': 'Database name is required'}), 400

    try:
        g.mongo_client = MongoDbClient(db_name)
        g.db = g.mongo_client.connect()
        current_app.logger.info('Database connection successful.')
    except Exception as e:
        current_app.logger.error(f"Error connecting to database: {str(e)}")
        return jsonify({'error': 'Database connection failed'}), 500

    current_app.logger.info(f"initialize_services took {time.time() - start_time} seconds")

@auth_check_bp.route('/auth_check', methods=['POST', 'OPTIONS', 'GET'])
def auth_check():
    """
    Checks if admin has granted access to the user
    """
    start_time = time.time()
    current_app.logger.info(f"auth_check called with method: {request.method}")
    
    if request.method == 'OPTIONS':
        return jsonify({}), 200 
    
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
    
    if request.method == 'POST':
        current_app.logger.info('Post request received')
        try:
            json_data = request.get_json()
            current_app.logger.info(f"Received JSON data: {json_data}")
            uid = json_data.get('uid')
            user_doc = g.db['users'].find_one({'_id': uid})  
            auth_status = user_doc.get('authorized', False)
            current_app.logger.info(f"auth_check took {time.time() - start_time} seconds")
            return jsonify({'auth_status': auth_status})
        except Exception as e:
            current_app.logger.error(f"Unexpected error: {str(e)}")
            return jsonify({'error': 'An unexpected error occurred'}), 500
    
