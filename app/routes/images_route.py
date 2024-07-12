import io
from dotenv import load_dotenv
from flask import request, Blueprint, g, jsonify
import requests
from app.services.UserService import UserService
from app.agents.ImageManager import ImageManager
from app.services.MongoDbClient import MongoDbClient

load_dotenv()

images_bp = Blueprint('images', __name__)

@images_bp.before_request
def initialize_services():
    if request.method == 'OPTIONS':
        return ('', 204)
    db_name = request.headers.get('dbName')
    if not db_name:
        return jsonify({"error": "dbName is required in the headers"}), 400
    g.uid = request.headers.get('uid')
    g.mongo_client = MongoDbClient(db_name)
    db = g.mongo_client.connect()
    g.user_service = UserService(db)
    g.image_manager = ImageManager(db, g.uid)
            

@images_bp.route('/images', methods=['GET', 'POST', 'DELETE', 'PUT', 'PATCH', 'OPTIONS'])
def images():
    if request.method == "POST":
        image_request = request.get_json()
        image_url = g.image_manager.generate_image(image_request)
        return (image_url, 200)
    
    if request.method == "GET":
        images_list = g.user_service.fetch_all_from_dalle_images(g.uid)
        return (images_list, 200)
    
    if request.method == "DELETE":
        path = request.get_json()
        g.user_service.delete_generated_image_from_firebase_storage(path)
        return ({'message': 'Image deleted successfully'}, 200)

@images_bp.route('/images/save', methods=['POST'])
def save_image():    
    data = request.get_json()
    url = data.get('image')  
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        return ({'error': 'Failed to fetch image'}, 400)
    image_data = response.content
    image_blob = io.BytesIO(image_data)
    image_url = g.user_service.upload_generated_image_to_firebase_storage(image_blob, g.uid)
    return (image_url, 200)