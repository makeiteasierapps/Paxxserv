import os
import certifi
from flask import Blueprint, request, jsonify
from firebase_admin import credentials, initialize_app
from pymongo import MongoClient
from app.services.FirebaseService import FirebaseService
from dotenv import load_dotenv

load_dotenv()

auth_check_bp = Blueprint('auth_check', __name__)

cred = credentials.Certificate(os.getenv('FIREBASE_ADMIN_SDK'))

initialize_app(cred, {
    'projectId': 'paxxiumv1',
    'storageBucket': 'paxxiumv1.appspot.com'
})

# MongoDB URI
mongo_uri = os.getenv('MONGO_URI')
# Create a new MongoClient and connect to the server
client = MongoClient(mongo_uri, tlsCAFile=certifi.where())

db = client['paxxium']

firebase_service = FirebaseService()

os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

@auth_check_bp.route('/auth_check', methods=['POST', 'OPTIONS', 'GET'])
def auth_check():
    """
    Checks if admin has granted access to the user
    """
    if request.method == 'OPTIONS':
        return ('', 204)
    
    if request.method == 'POST':
        uid = request.json.get('uid')
        user_doc = db['users'].find_one({'_id': uid})  
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