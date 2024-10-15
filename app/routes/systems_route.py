from typing import Any, List
import logging
import json
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from app.services.SystemService import SystemService
from app.services.UserService import UserService

router = APIRouter()

class ConfigFileUpdate(BaseModel):
    path: str
    content: str
    category: str

class FileCheckRequest(BaseModel):
    filename: str

def get_db(request: Request):
    try:
        mongo_client = request.app.state.mongo_client
        db = mongo_client.db
        return db
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

def get_user_service(db: Any = Depends(get_db)):
    return UserService(db)

def get_system_service(
    db: Any = Depends(get_db),
    user_service: UserService = Depends(get_user_service),
    uid: str = Header(...)
):
    return SystemService(db, user_service, uid)

@router.get('/config-files', response_model=List[ConfigFileUpdate])
async def get_config_files(system_service: SystemService = Depends(get_system_service)):
    try:
        config_files = system_service.config_files
        return JSONResponse(content=config_files, status_code=200)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while fetching config files: {str(e)}")

@router.put('/config-files')
async def write_config_file(
    file_update: ConfigFileUpdate,
    system_service: SystemService = Depends(get_system_service)
):
    try:
        result = await system_service.write_config_file(file_update.path, file_update.content, file_update.category)
        logging.info(f"Config file update result: {result}")
        
        # Convert result to a JSON string
        result_json = json.dumps(result)
        
        # Set headers explicitly
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(result_json))
        }
        
        # Return a raw Response object
        return Response(content=result_json, status_code=200, headers=headers)
    except HTTPException as he:
        logging.error(f"HTTP Exception in write_config_file: {str(he)}")
        raise he
    except Exception as e:
        logging.error(f"Unexpected error in write_config_file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred while writing to the config file: {str(e)}")