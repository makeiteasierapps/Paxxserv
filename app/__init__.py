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

socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')

def create_app():
    app = Flask(__name__)
    CORS(app)

    from .routes.chat_route import chat_bp
    from .routes.sam_route import sam_bp
    from .routes.moments_route import moment_bp
    from .routes.auth_check_route import auth_check_bp
    from .routes.images_route import images_bp
    from .routes.news_routes import news_bp
    from .routes.signup_route import signup_bp
    from .routes.profile_route import profile_bp
    from .routes.kb_route import kb_bp
    app.register_blueprint(chat_bp)
    app.register_blueprint(sam_bp)
    app.register_blueprint(moment_bp)
    app.register_blueprint(auth_check_bp)
    app.register_blueprint(images_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(signup_bp)
    app.register_blueprint(kb_bp)

    socketio.init_app(app)
    return app