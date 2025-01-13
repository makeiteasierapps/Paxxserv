import json
from app.services.ChatService import ChatService
from app.services.ExtractionService import ExtractionService
from app.services.KnowledgeBaseService import KnowledgeBaseService
from app.services.LocalStorageService import LocalStorageService
from app.services.ProfileService import ProfileService
from app.agents.BossAgent import BossAgent
from app.agents.AnthropicClient import AnthropicClient
from app.agents.OpenAiClient import OpenAiClient
from app.services.MongoDbClient import MongoDbClient
from app.services.ColbertService import ColbertService
from app.services.KbDocumentService import KbDocumentService

def get_db():
    try:
        mongo_client = MongoDbClient.get_instance('paxxium')
        return mongo_client.db
    except Exception as e:
        raise Exception(f"Database connection failed: {str(e)}")

def initialize_services(db, uid):
    chat_service = ChatService(db)
    profile_service = ProfileService(db, uid)
    return chat_service, profile_service

def create_boss_agent(chat_settings, sio, db, uid, profile_service):
    if not chat_settings:
        return None

    chat_constants = chat_settings.get('chat_constants')
    use_profile_data = chat_settings.get('use_profile_data', False)
    model = chat_settings.get('agent_model')
    user_analysis = profile_service.get_user_analysis(uid) if use_profile_data else None

    if model.startswith('claude'):
        ai_client = AnthropicClient(db, uid)
    else:
        ai_client = OpenAiClient(db, uid)

    boss_agent = BossAgent(
        ai_client,
        sio,
        model=model,
        chat_constants=chat_constants,
        user_analysis=user_analysis
    )

    return boss_agent

def handle_extraction(urls, extraction_service, boss_agent):
    extracted_docs = []
    for url in urls:
        for result in extraction_service.extract_from_url(url, 'scrape'):
            result_dict = json.loads(result)
            if result_dict['status'] == 'completed':
                extracted_docs.append(result_dict['content'])
            elif result_dict['status'] == 'error':
                print(f"Error extracting from URL: {result_dict['message']}")
    if extracted_docs:
        extracted_docs_response = extraction_service.parse_extraction_response(extracted_docs)
        return boss_agent.prepare_url_content_for_ai(extracted_docs_response)
    return None

async def handle_chat(sio, sid, data):
    try:
        urls = data.get('urls', [])
        uid = data.get('uid')
        kb_id = data.get('kbId', None)
        chat_settings = data.get('chatSettings', None)
        user_message = data['userMessage']['content']
        chat_id = data['chatId']
        image_blob = data.get('imageBlob', None)
        file_name = data.get('fileName', None)
        system_message = None

        db = get_db()
        chat_service, profile_service = initialize_services(db, uid)
        boss_agent = create_boss_agent(chat_settings, sio, db, uid, profile_service)

        image_path = None
        if image_blob:
            await LocalStorageService.upload_file_async(image_blob, uid, 'chats', file_name)

        await chat_service.create_message(chat_id, 'user', user_message, image_path)
        async def save_agent_message(chat_id, message):
            await chat_service.create_message(chat_id, 'agent', message)

        if kb_id:
            kb_service = KnowledgeBaseService(db, uid, kb_id)
            colbert_service = ColbertService(kb_service.index_path)
            results = colbert_service.search_index(user_message)
            system_message = colbert_service.prepare_vector_response(results)

        if urls:
            kb_document_service = KbDocumentService(db, kb_id)
            extraction_service = ExtractionService(db, uid, kb_document_service)
            url_content = handle_extraction(urls, extraction_service, boss_agent)
            if url_content:
                boss_agent.chat_constants += "\n" + url_content

        await boss_agent.process_message(data['chatHistory'], chat_id, user_message, save_agent_message, image_blob)

    except Exception as e:
        await sio.emit('error', {"error": str(e)})

def setup_chat_handlers(sio):
    @sio.on('chat')
    async def chat_handler(sid, data):
        await handle_chat(sio, sid, data)