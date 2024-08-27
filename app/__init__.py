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

socketio = SocketIO(cors_allowed_origins="*", async_mode='gevent')

def create_app():
    app = Flask(__name__)

    socketio.init_app(app)
    
    # Register blueprints
    from .routes import chat_route, sam_route, moments_route, auth_check_route, images_route, news_routes, signup_route, profile_route, kb_route
    
    blueprints = [
        (chat_route.chat_bp, chat_route.cors),
        (sam_route.sam_bp, sam_route.cors),
        (moments_route.moment_bp, moments_route.cors),
        (auth_check_route.auth_check_bp, auth_check_route.cors),
        (images_route.images_bp, images_route.cors),
        (profile_route.profile_bp, profile_route.cors),
        (news_routes.news_bp, news_routes.cors),
        (signup_route.signup_bp, signup_route.cors),
        (kb_route.kb_bp, kb_route.cors)
    ]
    
    for blueprint, cors in blueprints:
        cors.init_app(blueprint)
        app.register_blueprint(blueprint)

    from .routes import socket
    
    return app