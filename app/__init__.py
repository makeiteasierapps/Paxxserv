from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS

socketio = SocketIO(cors_allowed_origins="*")

def create_app():
    app = Flask(__name__)
    CORS(app)

    from .routes.chat_route import chat_bp
    app.register_blueprint(chat_bp)

    socketio.init_app(app)  # Initialize SocketIO with the app

    return app