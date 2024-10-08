import os
from fastapi import APIRouter, Depends
from app.services.SystemService import SystemService
from app.services.UserService import UserService

router = APIRouter()

import os
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, List
from app.services.SystemService import SystemService
from app.services.UserService import UserService

router = APIRouter()

class ConfigFileContent(BaseModel):
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

@router.get('/config-files', response_model=List[str])
async def list_config_files(uid: str, system_service: SystemService = Depends(get_system_service)):
    try:
        config_files = await system_service.list_config_files(uid)
        return config_files
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while listing config files: {str(e)}")

@router.get('/config-files/{filename}')
async def read_config_file(uid: str, filename: str, system_service: SystemService = Depends(get_system_service)):
    try:
        content = await system_service.read_config_file(uid, filename)
        return JSONResponse(content={'content': content}, status_code=200)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while reading the config file: {str(e)}")

@router.put('/config-files/{filename}')
async def write_config_file(uid: str, filename: str, file_content: ConfigFileContent, system_service: SystemService = Depends(get_system_service)):
    try:
        result = await system_service.write_config_file(uid, filename, file_content.content)
        return JSONResponse(content=result, status_code=200)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while writing to the config file: {str(e)}")