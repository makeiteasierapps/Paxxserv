from flask import Flask

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config_name)

    from .routes.chat_route import chat_bp
    app.register_blueprint(chat_bp)

    return app