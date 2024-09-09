from dotenv import load_dotenv
from fastapi import APIRouter, Header, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from app.agents.OpenAiClient import OpenAiClient
from app.agents.ContentProcessor import ContentProcessor
from app.services.MomentService import MomentService
from app.services.MongoDbClient import MongoDbClient

load_dotenv()
router = APIRouter(prefix="/api")

class Moment(BaseModel):
    momentId: Optional[str]
    date: str
    transcript: str
    actionItems: List[str] = []
    summary: Optional[str]

def get_db(dbName: str = Header(...)):
    try:
        mongo_client = MongoDbClient(dbName)
        db = mongo_client.connect()
        return db
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

def get_services(db = Depends(get_db)):
    moment_service = MomentService(db)
    openai_client = OpenAiClient()
    return moment_service, openai_client

@router.get("/moments")
async def handle_fetch_moments(services: tuple = Depends(get_services)):
    moment_service, _ = services
    all_moments = moment_service.get_all_moments()
    return JSONResponse(content=all_moments, status_code=200)

@router.post("/moments")
async def handle_add_moment(new_moment: Moment, services: tuple = Depends(get_services)):
    moment_service, openai_client = services
    content_processor = ContentProcessor(model='gpt-4o')
    
    processed_moment = {**new_moment.dict(), **content_processor.extract_content(new_moment.dict())}
    new_moment = moment_service.add_moment(processed_moment)
    
    combined_content = f"Transcript: {new_moment['transcript']}\nAction Items:\n" + "\n".join(new_moment['actionItems']) + f"\nSummary: {new_moment['summary']}"
    snapshot_data = new_moment.copy()
    snapshot_data['embeddings'] = openai_client.embed_content(combined_content)
    
    moment_service.create_snapshot(snapshot_data)
    
    return JSONResponse(content=new_moment, status_code=200)

@router.put("/moments")
async def handle_update_moment(moment: Moment, services: tuple = Depends(get_services)):
    moment_service, openai_client = services
    content_processor = ContentProcessor(model='gpt-4o')
    
    current_snapshot = {**moment.dict(), **content_processor.extract_content(moment.dict())}
    previous_snapshot = moment_service.get_previous_snapshot(moment.momentId)

    combined_content = f"Transcript: {moment.transcript}\nAction Items:\n" + "\n".join(current_snapshot['actionItems']) + f"\nSummary: {current_snapshot['summary']}"
    current_snapshot['embeddings'] = openai_client.embed_content(combined_content)
    
    moment_service.create_snapshot(current_snapshot)

    new_snapshot = content_processor.diff_snapshots(previous_snapshot, current_snapshot)
    new_snapshot.update({
        'momentId': moment.momentId,
        'date': moment.date,
        'transcript': moment.transcript
    })

    new_snapshot['transcript'] = moment_service.update_moment(new_snapshot)
    return JSONResponse(content=new_snapshot, status_code=200)

@router.delete("/moments")
async def handle_delete_moment(moment_id: str, services: tuple = Depends(get_services)):
    moment_service, _ = services
    moment_service.delete_moment(moment_id)
    return JSONResponse(content={'message': 'Moment Deleted'}, status_code=200)