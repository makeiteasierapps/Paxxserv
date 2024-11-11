import os
from dotenv import load_dotenv
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.services.MongoDbClient import MongoDbClient
from app.services.FirebaseService import FirebaseService
load_dotenv(override=True)

router = APIRouter()

def get_db(request: Request):
    try:
        mongo_client = request.app.state.mongo_client
        db = mongo_client.db
        return db
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

@router.get("/auth_check")
async def get_firebase_config():
    """
    Fetches Firebase configuration
    """
    try:
        config = {
            "apiKey": os.getenv('FIREBASE_API_KEY'),
            "authDomain": os.getenv('FIREBASE_AUTH_DOMAIN'),
            "projectId": os.getenv('FIREBASE_PROJECT_ID'),
            "messagingSenderId": os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
            "appId": os.getenv('FIREBASE_APP_ID'),
        }
        
        missing_keys = [key for key, value in config.items() if value is None]
        if missing_keys:
            raise HTTPException(status_code=500, detail=f"Missing Firebase configuration keys: {', '.join(missing_keys)}")
        
        return JSONResponse(content=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while fetching the configuration: {str(e)}")

@router.post("/auth_check")
async def check_auth(request: Request, db: MongoDbClient = Depends(get_db)):
    """
    Checks if admin has granted access to the user
    """
    try:
        json_data = await request.json()
        uid = json_data.get('uid')
        user_doc = await db['users'].find_one({'_id': uid})
        
        if user_doc is None:
            raise HTTPException(status_code=404, detail="User not found")
            
        auth_status = user_doc.get('authorized', False)
        return JSONResponse(content={'auth_status': auth_status})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in POST handler: {str(e)}")

@router.post("/update_password")
async def update_password(request: Request):
    """
    Updates the user's password
    """
    try:
        json_data = await request.json()
        uid = json_data.get('uid')
        new_password = json_data.get('newPassword')
        FirebaseService.update_user_password(uid, new_password)
        return JSONResponse(content={'message': 'Password updated successfully'})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in POST handler: {str(e)}")