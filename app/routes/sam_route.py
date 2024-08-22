import os
from flask import Blueprint, Response, send_file, request
from app.agents.OpenAiClient import OpenAiClient

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
    openai_client = OpenAiClient()
    messages = [{
                "role": "user",
                "content": new_message,
            }]
    text_response = openai_client.generate_chat_completion(messages, model='gpt-4o')
    file_path = 'app/audioFiles/audio.mp3'
        
    # Delete the existing file if it exists
    if os.path.exists(file_path):
        os.remove(file_path)
    
    response = openai_client.get_audio_speech(
        model="tts-1",
        voice="nova",
        message=text_response,
    )

    response.stream_to_file(file_path)

    # for chunk in response.iter_bytes(chunk_size=4096):
    #     if chunk:
    #         yield chunk
    return send_file('audioFiles/audio.mp3', mimetype='audio/mpeg')
