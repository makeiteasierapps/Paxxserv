from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.services.UserService import UserService
from app.services.MongoDbClient import MongoDbClient
from pydantic import BaseModel

load_dotenv()

router = APIRouter(prefix="/api")

class SignupData(BaseModel):
    username: str
    uid: str
    openAiApiKey: str
    authorized: bool

def get_db(dbName: str = Header(...)):
    try:
        mongo_client = MongoDbClient(dbName)
        db = mongo_client.connect()
        return db
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

def get_user_service(db: MongoDbClient = Depends(get_db)):
    return UserService(db)

@router.post('/signup')
async def signup(data: SignupData, user_service: UserService = Depends(get_user_service)):
    try:
        updates = {   
            'username': data.username,
            'open_key': data.openAiApiKey,
            'authorized': data.authorized
        }
      
        user_service.update_user(data.uid, updates)

        return JSONResponse(content={'message': 'User added successfully'}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during signup: {str(e)}")