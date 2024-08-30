from fastapi import APIRouter, Depends, Header, HTTPException, File, UploadFile
from fastapi.responses import JSONResponse
from typing import Optional
from pydantic import BaseModel
from app.services.ChatService import ChatService
from app.services.FirebaseStoreageService import FirebaseStorageService as firebase_storage
from app.services.MongoDbClient import MongoDbClient

router = APIRouter()

def get_chat_service(dbName: str = Header(...), uid: str = Header(...)):
    try:
        mongo_client = MongoDbClient(dbName)
        db = mongo_client.connect()
        return ChatService(db), uid
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

class ChatData(BaseModel):
    uid: str
    chatName: str
    agentModel: str
    systemPrompt: Optional[str] = None
    chatConstants: Optional[dict] = None
    useProfileData: Optional[bool] = None

class DeleteChatData(BaseModel):
    chatId: str

class UpdateSettingsData(BaseModel):
    chatId: str
    # Add other fields as needed

@router.get("/chat")
async def get_all_chats(chat_service: ChatService = Depends(get_chat_service)):
    chat_service, uid = chat_service
    return JSONResponse(content=chat_service.get_all_chats(uid))

@router.post("/chat")
async def create_chat(data: ChatData, chat_service: ChatService = Depends(get_chat_service)):
    chat_service, _ = chat_service
    chat_id = chat_service.create_chat_in_db(
        data.uid, 
        data.chatName, 
        data.agentModel, 
        system_prompt=data.systemPrompt, 
        chat_constants=data.chatConstants, 
        use_profile_data=data.useProfileData
    )
    return JSONResponse(content={
        'chatId': chat_id,
        'chat_name': data.chatName,
        'agent_model': data.agentModel,
        'uid': data.uid,
        'system_prompt': data.systemPrompt,
        'chat_constants': data.chatConstants,
        'use_profile_data': data.useProfileData,
    })

@router.delete("/chat")
async def delete_chat(data: DeleteChatData, chat_service: ChatService = Depends(get_chat_service)):
    chat_service, _ = chat_service
    chat_service.delete_chat(data.chatId)
    return JSONResponse(content={'message': 'Conversation deleted'})

@router.patch("/chat/update_settings")
async def update_settings(data: UpdateSettingsData, chat_service: ChatService = Depends(get_chat_service)):
    chat_service, _ = chat_service
    chat_service.update_settings(data.chatId, **data.dict(exclude={'chatId'}))
    return JSONResponse(content={'message': 'Conversation settings updated'})

@router.delete("/messages")
async def delete_all_messages(data: DeleteChatData, chat_service: ChatService = Depends(get_chat_service)):
    chat_service, _ = chat_service
    chat_service.delete_all_messages(data.chatId)
    return JSONResponse(content={'message': 'Memory Cleared'})

@router.post("/messages/utils")
async def upload_image(file: UploadFile = File(...), uid: str = Header(...)):
    file_url = firebase_storage.upload_file(file.file, uid, 'gpt-vision')
    return JSONResponse(content={'fileUrl': file_url})