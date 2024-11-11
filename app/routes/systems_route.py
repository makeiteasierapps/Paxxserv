from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.services.System.SystemService import SystemService
from app.agents.SystemAgent import SystemAgent
from app.services.System.SystemIndexManager import SystemIndexManager
from app.services.ColbertService import ColbertService
router = APIRouter()

class FileCommandsUpdate(BaseModel):
    path: str
    restartCommand: Optional[str] = None
    testCommand: Optional[str] = None 

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

def get_colbert_service(
    uid: str = Header(...)
):
    return ColbertService(uid=uid)

async def get_system_service(
    request: Request,
    uid: str = Header(...)
) -> SystemService:
    system_manager = request.app.state.system_state_manager
    service = SystemService(system_manager, uid)
    await service.initialize()
    return service

@router.put('/file-commands')
async def update_file_commands(
    file_commands: FileCommandsUpdate,
    system_service: SystemService = Depends(get_system_service)
):
    # Convert camelCase to snake_case for internal use
    await system_service.update_file_commands(
        file_path=file_commands.path,
        restart_command=file_commands.restartCommand,
        test_command=file_commands.testCommand
    )
    return {"status": "success"}
@router.get('/system-health')
async def get_system_health(
    system_service: SystemService = Depends(get_system_service)
):
    try:
        health_status = await system_service.check_systemd_services()
        return JSONResponse(content=health_status, status_code=200)
    except HTTPException as e:
        raise e

@router.get('/config-files', response_model=List[ConfigFileUpdate])
async def get_config_files(
    system_service: SystemService = Depends(get_system_service),
    colbert_service: ColbertService = Depends(get_colbert_service)
):
    try:
        config_files = await system_service.system_manager.get_config_files()
        # system_index_manager = SystemIndexManager(system_service, colbert_service)
        # prepared_data = system_index_manager.prepare_config_files_for_indexing()
        # index_result = system_index_manager.create_system_index(prepared_data)
        # system_service.config_db.add_index_path(index_result.get('index_path'))
        # print(index_result)
        # system_agent = SystemAgent()
        # category_routing = system_agent.category_routing('will you look over my mongodb config and see how I can improve it?', system_service.config_categories)
        # print(category_routing)
        # combined_files = await system_service.combine_config_files_by_category()
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
        print(result)
        return JSONResponse(content=result, status_code=200)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while writing to the config file: {str(e)}")
