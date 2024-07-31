from dotenv import load_dotenv
import os
from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS
from firebase_admin import credentials, initialize_app

load_dotenv()
cred = credentials.Certificate(os.getenv('FIREBASE_ADMIN_SDK'))

try:
    initialize_app(cred, {
        'projectId': 'paxxiumv1',
        'storageBucket': 'paxxiumv1.appspot.com'
    })
except ValueError:
    pass

socketio = SocketIO(cors_allowed_origins="*")

def create_app():
    app = Flask(__name__)
    CORS(app)
    socketio.init_app(app)

    # Register blueprints
    from .routes import chat_route, sam_route, moments_route, auth_check_route, images_route, news_routes, signup_route, profile_route, kb_route
    
    blueprints = [
        chat_route.chat_bp, sam_route.sam_bp, moments_route.moment_bp,
        auth_check_route.auth_check_bp, images_route.images_bp,
        profile_route.profile_bp, news_routes.news_bp,
        signup_route.signup_bp, kb_route.kb_bp
    ]
    
    for blueprint in blueprints:
        app.register_blueprint(blueprint)
    return app