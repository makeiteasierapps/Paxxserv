import json
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from app.utils.custom_json_encoder import CustomJSONEncoder
from app.services.ChatService import ChatService
from fastapi import Request

class ChatData(BaseModel):
    uid: str

class DeleteChatData(BaseModel):
    chatId: str

class UpdateSettingsData(BaseModel):
    chatId: str

    class Config:
        extra = 'allow'

def create_chat_router(prefix: str = "", chat_type: str = "default"):
    router = APIRouter(prefix=f"{prefix}/chat")
    
    def get_specific_chat_service(request: Request, uid: str = Header(...)):
        try:
            print(f"Creating chat router with prefix: {prefix}")
            print(f"Chat type: {chat_type}")
            mongo_client = request.app.state.mongo_client
            db = mongo_client.db
            return ChatService(db, chat_type=chat_type), uid
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

    @router.get("")  # /chat or /system/chat
    async def get_all_chats(chat_service=Depends(get_specific_chat_service)):
        chat_service, uid = chat_service
        chats = await chat_service.get_all_chats(uid)
        json_chats = jsonable_encoder(chats)
        json_str = json.dumps(json_chats, cls=CustomJSONEncoder)
        return JSONResponse(content=json.loads(json_str))

    @router.post("")  # /chat or /system/chat
    async def create_chat(data: ChatData, chat_service=Depends(get_specific_chat_service)):
        chat_service, _ = chat_service
        chat_data = await chat_service.create_chat_in_db(data.uid)
        return JSONResponse(content=chat_data)

    @router.delete("")  # /chat or /system/chat
    async def delete_chat(data: DeleteChatData, chat_service=Depends(get_specific_chat_service)):
        chat_service, _ = chat_service
        await chat_service.delete_chat(data.chatId)
        return JSONResponse(content={'message': 'Conversation deleted'})

    @router.patch("/update_settings")  # /chat/update_settings or /system/chat/update_settings
    async def update_settings(data: UpdateSettingsData, chat_service=Depends(get_specific_chat_service)):
        chat_service, _ = chat_service
        await chat_service.update_settings(data.chatId, **data.model_dump(exclude={'chatId', 'uid'}))
        return JSONResponse(content={'message': 'Conversation settings updated'})

    @router.delete("/messages")  # /chat/messages or /system/chat/messages
    async def delete_all_messages(data: DeleteChatData, chat_service=Depends(get_specific_chat_service)):
        chat_service, _ = chat_service
        await chat_service.delete_all_messages(data.chatId)
        return JSONResponse(content={'message': 'Memory Cleared'})

    return router