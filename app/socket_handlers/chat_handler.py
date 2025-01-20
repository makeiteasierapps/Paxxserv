import json
import sys
import traceback
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

    system_message = chat_settings.get('system_message', '')
    use_profile_data = chat_settings.get('use_profile_data', False)
    model = chat_settings.get('agent_model')
    context_urls = chat_settings.get('context_urls', [])
    user_analysis = profile_service.get_user_analysis(uid) if use_profile_data else None

    if model.startswith('claude'):
        ai_client = AnthropicClient(db, uid)
    else:
        ai_client = OpenAiClient(db, uid)

    boss_agent = BossAgent(
        ai_client,
        sio,
        model=model,
        system_message=system_message,
        user_analysis=user_analysis,
    )

    # Add URL content if it exists, but only for fully extracted URLs
    if context_urls:
        extracted_urls = [
            url_data for url_data in context_urls 
            if isinstance(url_data, dict) and 'url' in url_data and 'content' in url_data
        ]
        
        if extracted_urls:
            url_content = boss_agent.prepare_multiple_url_content(extracted_urls)
            if boss_agent.system_message:
                if "<<URL_CONTENT_START>>" in boss_agent.system_message:
                    start_idx = boss_agent.system_message.find("<<URL_CONTENT_START>>")
                    end_idx = boss_agent.system_message.find("<<URL_CONTENT_END>>") + len("<<URL_CONTENT_END>>")
                    boss_agent.system_message = (
                        boss_agent.system_message[:start_idx] + 
                        url_content + 
                        boss_agent.system_message[end_idx:]
                    )
                else:
                    boss_agent.system_message += "\n" + url_content
            else:
                boss_agent.system_message = url_content

    return boss_agent

async def handle_extraction(urls, db, uid, boss_agent):
    extraction_service = ExtractionService(db, uid)
    url_contents = []
    urls_to_extract = []
    
    # First separate already extracted URLs from ones that need extraction
    for url_item in urls:
        if isinstance(url_item, dict) and 'url' in url_item and 'content' in url_item:
            # Already extracted URL - keep as is
            url_contents.append(url_item)
        else:
            # New URL that needs extraction
            url = url_item['url'] if isinstance(url_item, dict) else url_item
            urls_to_extract.append(url)
    
    # Only perform extraction for new URLs
    if urls_to_extract:
        for url in urls_to_extract:
            url_extracted_docs = []
            for result in await extraction_service.extract_from_url(url, 'scrape', for_kb=False):
                url_extracted_docs.append(result)
                
            if url_extracted_docs:
                docs_response = extraction_service.parse_extraction_response(url_extracted_docs)
                url_contents.append({
                    'url': url,
                    'content': docs_response['content']
                })
    
    # Update boss_agent's system message with all content
    if url_contents:
        formatted_content = boss_agent.prepare_multiple_url_content(url_contents)
        if boss_agent.system_message:
            if "<<URL_CONTENT_START>>" in boss_agent.system_message:
                start_idx = boss_agent.system_message.find("<<URL_CONTENT_START>>")
                end_idx = boss_agent.system_message.find("<<URL_CONTENT_END>>") + len("<<URL_CONTENT_END>>")
                boss_agent.system_message = (
                    boss_agent.system_message[:start_idx] + 
                    formatted_content + 
                    boss_agent.system_message[end_idx:]
                )
            else:
                boss_agent.system_message += "\n" + formatted_content
        else:
            boss_agent.system_message = formatted_content
    
    return url_contents

async def handle_chat(sio, sid, data):
    print(data)

    try:
        chat_settings = data.get('selectedChat', None)
        if not chat_settings:
            await sio.emit('error', {"error": "Chat settings are missing"})
            return

        uid = chat_settings.get('uid')
        chat_id = chat_settings.get('chatId')
        messages = chat_settings.get('messages', [])
        context_urls = chat_settings.get('context_urls', [])
        
        if not uid or not chat_id or not messages:
            await sio.emit('error', {"error": "Missing required chat parameters"})
            return
            
        user_message = messages[0].get('content') if messages else None
        if not user_message:
            await sio.emit('error', {"error": "Message content is missing"})
            return

        kb_id = data.get('kbId', None)
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

        if len(context_urls) > 0:
            context_urls = await handle_extraction(context_urls, db, uid, boss_agent)
            update_settings = {'context_urls': context_urls}
            await chat_service.update_settings(chat_id, **update_settings)
            await sio.emit('context_urls', context_urls)

        await boss_agent.process_message(chat_settings['messages'], chat_id, user_message, save_agent_message, image_blob)

    except Exception as e:
        # Get the full stack trace
        exc_type, exc_value, exc_traceback = sys.exc_info()
        stack_trace = traceback.format_exception(exc_type, exc_value, exc_traceback)
        
        error_details = {
            "error": str(e),
            "type": exc_type.__name__,
            "stack_trace": stack_trace,
            "location": "handle_chat"
        }
        print(f"Error details: {json.dumps(error_details, indent=2)}")
        await sio.emit('error', error_details)

def setup_chat_handlers(sio):
    @sio.on('chat')
    async def chat_handler(sid, data):
        await handle_chat(sio, sid, data)