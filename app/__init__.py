from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS

socketio = SocketIO(cors_allowed_origins="*", async_mode='gevent')

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
    app.register_blueprint(chat_bp)
    app.register_blueprint(sam_bp)
    app.register_blueprint(moment_bp)
    app.register_blueprint(auth_check_bp)
    app.register_blueprint(images_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(signup_bp)

    socketio.init_app(app)
    return app