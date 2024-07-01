from flask import Blueprint, Response, send_file, request
from app.agents.BossAgent import BossAgent

sam_bp = Blueprint('sam', __name__)


@sam_bp.route('/sam', methods=['OPTIONS'])
def handle_socketio_options():
    response = Response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@sam_bp.route('/sam', methods=['POST'])
def handle_new_message():
    new_message = request.json['newMessage']
    boss_agent = BossAgent(model='gpt-4o')
    get_text_response = boss_agent.get_full_response(new_message)
    boss_agent.stream_audio_response(get_text_response)
    return send_file('audioFiles/audio.mp3', mimetype='audio/mpeg')