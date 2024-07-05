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
})

# MongoDB URI
mongo_uri = os.getenv('MONGO_URI')
# Create a new MongoClient and connect to the server
client = MongoClient(mongo_uri, tlsCAFile=certifi.where())

db = client['paxxium']

firebase_service = FirebaseService()

os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

@auth_check_bp.route('/auth_check', methods=['POST', 'OPTIONS'])
def auth_check():
    """
    Checks if admin has granted access to the user
    """
    if request.method == 'OPTIONS':
        return ('', 204)

    id_token = request.headers.get('Authorization')
    if not id_token:
        return ('Missing token', 403)

    decoded_token = firebase_service.verify_id_token(id_token)
    if not decoded_token:
        return ('Invalid token', 403)

    uid = decoded_token['uid']
    print(uid)
    user_doc = db['users'].find_one({'_id': uid})  
    auth_status = user_doc.get('authorized', False)
    return jsonify({'auth_status': auth_status})