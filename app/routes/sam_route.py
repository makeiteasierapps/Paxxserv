import os
from fastapi import APIRouter, Response, Request, HTTPException
from fastapi.responses import FileResponse
from app.agents.OpenAiClient import OpenAiClient

router = APIRouter()

@router.options("/sam")
async def handle_socketio_options():
    response = Response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@router.post("/sam")
async def handle_new_message(request: Request):
    try:
        json_data = await request.json()
        new_message = json_data['newMessage']
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

        return FileResponse(file_path, media_type='audio/mpeg')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
