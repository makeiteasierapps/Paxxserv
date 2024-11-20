import json
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from app.utils.custom_json_encoder import CustomJSONEncoder
from app.services.ChatService import ChatService
from fastapi import Request

router = APIRouter()

def get_chat_service(request: Request, dbName: str = Header(...), uid: str = Header(...)):
    try:
        mongo_client = request.app.state.mongo_client
        db = mongo_client.db
        return ChatService(db), uid
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

class ChatData(BaseModel):
    uid: str

class DeleteChatData(BaseModel):
    chatId: str

class UpdateSettingsData(BaseModel):
    chatId: str

    class Config:
        extra = 'allow'


@router.get("/chat")
async def get_all_chats(chat_service: ChatService = Depends(get_chat_service)):
    chat_service, uid = chat_service
    chats = await chat_service.get_all_chats(uid)
    json_chats = jsonable_encoder(chats)
    json_str = json.dumps(json_chats, cls=CustomJSONEncoder)
    return JSONResponse(content=json.loads(json_str))

@router.post("/chat")
async def create_chat(data: ChatData, chat_service: ChatService = Depends(get_chat_service)):
    chat_service, _ = chat_service
    chat_data = await chat_service.create_chat_in_db(
        data.uid,
    )
    return JSONResponse(content={
        'chatId': CustomJSONEncoder().default(chat_data['_id']),
        'chat_name': chat_data['chat_name'],
        'agent_model': chat_data['agent_model'],
        'uid': data.uid,
    })

@router.delete("/chat")
async def delete_chat(data: DeleteChatData, chat_service: ChatService = Depends(get_chat_service)):
    chat_service, _ = chat_service
    await chat_service.delete_chat(data.chatId)
    return JSONResponse(content={'message': 'Conversation deleted'})

@router.patch("/chat/update_settings")
async def update_settings(data: UpdateSettingsData, chat_service: ChatService = Depends(get_chat_service)):
    chat_service, _ = chat_service
    await chat_service.update_settings(data.chatId, **data.model_dump(exclude={'chatId', 'uid'}))
    return JSONResponse(content={'message': 'Conversation settings updated'})

@router.delete("/messages")
async def delete_all_messages(data: DeleteChatData, chat_service: ChatService = Depends(get_chat_service)):
    chat_service, _ = chat_service
    await chat_service.delete_all_messages(data.chatId)
    return JSONResponse(content={'message': 'Memory Cleared'})
