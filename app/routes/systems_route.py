from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.agents.CategoryAgent import CategoryAgent
from app.services.SystemService import SystemService
from app.services.UserService import UserService

router = APIRouter()

CATEGORIES = [
    "NGINX Configuration",
    "SystemD Service Files",
    "FSTAB for File System Mounting",
    "SSH Configuration",
    "DNS and Networking",
    "Logrotate for Log Management",
    "User and Group Configuration",
    "Sysctl for Kernel Parameters",
    "Environment Variables",
    "Fail2ban Configuration"
]

class ConfigFileUpdate(BaseModel):
    filename: str
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
        result = await system_service.write_config_file(file_update.filename, file_update.content, file_update.category)
        return JSONResponse(content=result, status_code=200)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while writing to the config file: {str(e)}")
    
@router.post('/config-files/check')
async def check_if_config_file_exists_on_server(
    file_check: FileCheckRequest,
    system_service: SystemService = Depends(get_system_service)
):
    try:
        result = await system_service.check_if_config_file_exists_on_server(file_check.filename)
        if result:
            content = await system_service.read_config_file(file_check.filename)
            category_agent = CategoryAgent()
            result_obj = category_agent.does_file_belong_in_category(file_check.filename, CATEGORIES)
            if result_obj["belongs"] == True:
                return JSONResponse(content={"exists": True, "content": content, "category": result_obj["category"]}, status_code=200)
            else:
                new_category = category_agent.create_new_category(file_check.filename)
                return JSONResponse(content={"exists": True, "content": content, "category": new_category}, status_code=200)
        else:
            return JSONResponse(content={"exists": False}, status_code=200)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while checking if the config file exists: {str(e)}")