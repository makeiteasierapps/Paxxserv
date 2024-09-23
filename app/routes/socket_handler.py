from typing import List
import json
import socketio
from fastapi import HTTPException
from app.services.ChatService import ChatService
from app.services.LocalStorageService import LocalStorageService
from app.services.ProfileService import ProfileService
from app.agents.BossAgent import BossAgent
from app.agents.AnthropicClient import AnthropicClient
from app.agents.OpenAiClient import OpenAiClient
from app.services.MongoDbClient import MongoDbClient
from app.services.ExtractionService import ExtractionService
from app.services.KnowledgeBaseService import KnowledgeBaseService
from app.services.ColbertService import ColbertService
def get_db(dbName: str):
    try:
        mongo_client = MongoDbClient(dbName)
        db = mongo_client.connect()
        return db
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

def initialize_services(db, uid):
    chat_service = ChatService(db)
    profile_service = ProfileService(db, uid)
    kb_service = KnowledgeBaseService(db, uid)
    extraction_service = ExtractionService(db, uid)
    return chat_service, profile_service, kb_service, extraction_service

def create_boss_agent(chat_settings, sio, db, uid, profile_service):
    if not chat_settings:
        return None, None

    chat_constants = chat_settings.get('chat_constants')
    use_profile_data = chat_settings.get('use_profile_data', False)
    model = chat_settings.get('agent_model')
    user_analysis = profile_service.get_user_analysis(uid) if use_profile_data else None

    if model.startswith('claude'):
        ai_client = AnthropicClient(db, uid)
    else:
        ai_client = OpenAiClient(db, uid)

    boss_agent = BossAgent(
        ai_client=ai_client,
        sio=sio,
        model=model,
        chat_constants=chat_constants,
        user_analysis=user_analysis
    )

    return boss_agent

def handle_extraction(urls: List[str], extraction_service, kb_id, kb_service, boss_agent):
    extracted_docs = []
    for url in urls:
        for result in extraction_service.extract_from_url(url, kb_id, 'scrape', kb_service):
            result_dict = json.loads(result)
            if result_dict['status'] == 'completed':
                extracted_docs.append(result_dict['content'])
            elif result_dict['status'] == 'error':
                print(f"Error extracting from URL: {result_dict['message']}")
    if extracted_docs:
        extracted_docs_response = extraction_service.parse_extraction_response(extracted_docs)
        return boss_agent.prepare_url_content_for_ai(extracted_docs_response)
    return None

def setup_socketio_events(sio: socketio.AsyncServer):
    @sio.event
    async def chat(sid, data):
        try:
            urls = data.get('urls', [])
            uid = data.get('uid')
            save_to_db = data.get('saveToDb', False)
            kb_id = data.get('kbId', None)
            chat_settings = data.get('chatSettings', None)
            db_name = data.get('dbName')
            user_message = data['userMessage']['content']
            chat_id = data['chatId']
            image_blob = data.get('imageBlob', None)
            file_name = data.get('fileName', None)
            system_message = None

            if save_to_db and not db_name:
                await sio.emit('error', {"error": "dbName is required when saveToDb is true"})
                return

            db = get_db(db_name)
            chat_service, profile_service, kb_service, extraction_service = initialize_services(db, uid)
            boss_agent = create_boss_agent(chat_settings, sio, db, uid, profile_service)

            image_path = None
            if image_blob:
                image_info = await LocalStorageService.upload_file_async(image_blob, uid, 'chats', file_name)
                image_path = image_info['path']
                boss_agent.image_path = image_path
            
            if save_to_db:
                chat_service.create_message(chat_id, 'user', user_message, image_path)
                async def save_agent_message(chat_id, message):
                    chat_service.create_message(chat_id, 'agent', message)
                    await sio.emit('agent_message', {"type": "agent_message", "content": message})
            else:
                async def save_agent_message(chat_id, message):
                    await sio.emit('agent_message', {"type": "agent_message", "content": message})

            if kb_id:
                kb_service.set_kb_id(kb_id)
                colbert_service = ColbertService(kb_service.get_index_path())
                results = colbert_service.search_index(user_message)
                system_message = colbert_service.prepare_vector_response(results)

            if urls:
                system_message = handle_extraction(urls, extraction_service, kb_id, kb_service, boss_agent)

            await boss_agent.process_message(data['chatHistory'], chat_id, user_message, system_message, save_agent_message, image_blob)

        except Exception as e:
            await sio.emit('error', {"error": str(e)})

    @sio.event
    async def connect(sid, environ):
        print(f"Client connected: {sid}")

    @sio.event
    async def disconnect(sid):
        print(f"Client disconnected: {sid}")