import io
from dotenv import load_dotenv
from flask import request, Blueprint, g
import requests
from app.agents.BossAgent import BossAgent
from app.services.UserService import UserService

load_dotenv()

images_bp = Blueprint('images', __name__)

@images_bp.before_request
def initialize_services():
    db_name = request.headers.get('dbName', 'paxxium')
    g.user_service = UserService(db_name=db_name)

@images_bp.route('/images', methods=['GET', 'POST', 'DELETE', 'PUT', 'PATCH', 'OPTIONS'])
def images():
    if request.method == "OPTIONS":
        return ("", 204)
    uid = request.headers.get('uid')
    if request.method == "POST":
        image_request = request.get_json()
        encrypted_openai_key = g.user_service.get_keys(uid)
        openai_key = g.user_service.decrypt(encrypted_openai_key)
        image_agent = BossAgent(openai_key=openai_key)
    
        image_url = image_agent.generate_image(image_request)
        return (image_url, 200)
    
    if request.method == "GET":
        images_list = g.user_service.fetch_all_from_dalle_images(uid)
        return (images_list, 200)
    
    if request.method == "DELETE":
        path = request.get_json()
        g.user_service.delete_generated_image_from_firebase_storage(path)
        return ({'message': 'Image deleted successfully'}, 200)

@images_bp.route('/images/save', methods=['POST'])
def save_image():
    if request.method == "OPTIONS":
        return ("", 204)
    
    uid = request.headers.get('uid')
    
    data = request.get_json()
    url = data.get('image')  
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        return ({'error': 'Failed to fetch image'}, 400)
    image_data = response.content
    image_blob = io.BytesIO(image_data)
    image_url = g.user_service.upload_generated_image_to_firebase_storage(image_blob, uid)
    return (image_url, 200)