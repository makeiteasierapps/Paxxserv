from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.services.SystemService import SystemService
from app.services.UserService import UserService

router = APIRouter()

class ConfigFile(BaseModel):
    filename: str
    content: str

def get_db(request: Request):
    try:
        mongo_client = request.app.state.mongo_client
        db = mongo_client.db
        return db
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

def get_user_service(db: Any = Depends(get_db)):
    return UserService(db)

def get_system_service(db: Any = Depends(get_db), user_service: UserService = Depends(get_user_service)):
    return SystemService(db, user_service)

@router.get('/config-files', response_model=List[ConfigFile])
async def get_config_files(system_service: SystemService = Depends(get_system_service), uid: str = Header(...)):
    try:
        print(f"Fetching config files for user {uid}")
        config_files = await system_service.list_config_files(uid)
        print(f"Config files: {config_files}")
        result = await system_service.read_multiple_config_files(uid, config_files)
        return [ConfigFile(filename=item["filename"], content=item["content"]) for item in result]
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while fetching config files: {str(e)}")

@router.put('/config-files/{filename}')
async def write_config_file(uid: str, filename: str, file_content: ConfigFile, system_service: SystemService = Depends(get_system_service)):
    try:
        result = await system_service.write_config_file(uid, filename, file_content.content)
        return JSONResponse(content=result, status_code=200)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while writing to the config file: {str(e)}")